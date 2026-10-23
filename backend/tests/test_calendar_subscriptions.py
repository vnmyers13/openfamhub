"""Managed feed persistence, privacy, visibility, and RFC 5545 export contracts."""
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from icalendar import Calendar
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.integrations.calendar_relay import RelayFeed
from app.models.calendar_event import CalendarEvent
from app.models.calendar_source import CalendarSource
from app.models.calendar_subscription import CalendarSubscription, CalendarSubscriptionAudit
from app.services import calendar_subscriptions as subscriptions
from app.services import server_config

UTC = timezone.utc
NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
BACKEND = Path(__file__).resolve().parents[1]
SECRET_URL = "https://relay.example/c/" + "s" * 43 + ".ics"


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz else NOW.replace(tzinfo=None)

    monkeypatch.setattr(subscriptions, "datetime", Clock)


async def source(db, *, family_id="family", **values):
    row = CalendarSource(family_id=family_id, display_name="Private school source", **values)
    db.add(row)
    await db.flush()
    return row


async def event(db, src, title="Family dinner", **values):
    defaults = dict(
        family_id=src.family_id, start_dt=NOW, end_dt=NOW + timedelta(hours=1),
        created_at=NOW - timedelta(days=2), updated_at=NOW - timedelta(days=1),
    )
    defaults.update(values)
    row = CalendarEvent(source_id=src.id, title=title, **defaults)
    db.add(row)
    await db.flush()
    return row


def components(raw):
    return Calendar.from_ical(raw).walk("VEVENT")


async def test_render_exports_local_and_synced_events_not_deleted_or_disabled_sources(setup_db):
    local = await source(setup_db)
    school = await source(setup_db, provider="ical", ics_url="https://secret-source.example/token")
    disabled = await source(setup_db, enabled=False)
    deleted = await source(setup_db, is_deleted=True)
    await event(setup_db, local)
    await event(setup_db, school, "School concert", external_uid="private-upstream-uid")
    await event(setup_db, local, "Deleted event", is_deleted=True)
    await event(setup_db, disabled, "Disabled source event")
    await event(setup_db, deleted, "Deleted source event")
    raw = await subscriptions.render_ics(setup_db, "family", "full")
    assert {str(e["SUMMARY"]) for e in components(raw)} == {"Family dinner", "School concert"}
    assert b"secret-source" not in raw and b"private-upstream-uid" not in raw
    assert b"Private school source" not in raw


async def test_render_checks_both_event_and_source_family(setup_db):
    own = await source(setup_db)
    other = await source(setup_db, family_id="other")
    await event(setup_db, own, "Own")
    await event(setup_db, other, "Other")
    await event(setup_db, own, "Wrong event family", family_id="other")
    await event(setup_db, other, "Wrong source family", family_id="family")
    assert [str(e["SUMMARY"]) for e in components(await subscriptions.render_ics(setup_db, "family", "titles"))] == ["Own"]


async def test_render_uses_strict_overlap_across_the_stored_publication_horizon(setup_db):
    src = await source(setup_db)
    start, end = NOW - timedelta(days=90), NOW + timedelta(days=365)
    for title, a, b in [
        ("Overlaps past", start - timedelta(days=2), start + timedelta(seconds=1)),
        ("Overlaps future", end - timedelta(seconds=1), end + timedelta(days=2)),
        ("Ends at past", start - timedelta(days=1), start),
        ("Starts at future", end, end + timedelta(days=1)),
        ("Too old", start - timedelta(days=2), start - timedelta(days=1)),
        ("Too far ahead", end + timedelta(days=1), end + timedelta(days=2)),
    ]:
        await event(setup_db, src, title, start_dt=a, end_dt=b)
    raw = await subscriptions.render_ics(setup_db, "family", "full")
    assert [str(e["SUMMARY"]) for e in components(raw)] == ["Overlaps past", "Overlaps future"]


async def test_titles_omits_all_details_and_full_preserves_stored_details(setup_db):
    src = await source(setup_db)
    await event(setup_db, src, location="Library", description="Bring forms",
                url="https://event.example/details", organizer="School office",
                attendees=["Pat", "sam@example.com"], created_by="private-user-id")
    titles = await subscriptions.render_ics(setup_db, "family", "titles")
    full = await subscriptions.render_ics(setup_db, "family", "full")
    title_event, = components(titles)
    full_event, = components(full)
    assert set(title_event) <= {"UID", "SUMMARY", "DTSTART", "DTEND", "DTSTAMP", "LAST-MODIFIED", "SEQUENCE"}
    for field in ("DESCRIPTION", "LOCATION", "URL", "ORGANIZER", "ATTENDEE"):
        assert field not in title_event
    assert str(full_event["DESCRIPTION"]) == "Bring forms"
    assert str(full_event["LOCATION"]) == "Library"
    assert str(full_event["URL"]) == "https://event.example/details"
    assert str(full_event["ORGANIZER"].params["CN"]) == "School office"
    assert [str(a.params["CN"]) for a in full_event["ATTENDEE"]] == ["Pat", "sam@example.com"]
    assert str(full_event["ATTENDEE"][1]) == "mailto:sam@example.com"
    assert b"private-user-id" not in full and b"Private school source" not in full
    assert title_event["UID"] == full_event["UID"]


async def test_all_day_uses_date_only_exclusive_end_and_byte_stable_serialization(setup_db):
    src = await source(setup_db)
    await event(setup_db, src, all_day=True,
                start_dt=datetime(2026, 10, 23, tzinfo=UTC), end_dt=datetime(2026, 10, 25, tzinfo=UTC))
    first = await subscriptions.render_ics(setup_db, "family", "full")
    assert first == await subscriptions.render_ics(setup_db, "family", "full")
    assert b"DTSTART;VALUE=DATE:20261023\r\n" in first
    assert b"DTEND;VALUE=DATE:20261025\r\n" in first
    exported, = components(first)
    assert exported.decoded("DTSTART") == date(2026, 10, 23)
    assert exported.decoded("DTEND") == date(2026, 10, 25)


async def test_timed_values_are_utc_and_modified_data_comes_from_the_event(setup_db):
    src = await source(setup_db)
    await event(setup_db, src, start_dt=datetime(2026, 10, 23, 8, tzinfo=timezone(timedelta(hours=-4))),
                end_dt=datetime(2026, 10, 23, 9, tzinfo=timezone(timedelta(hours=-4))))
    raw = await subscriptions.render_ics(setup_db, "family", "titles")
    assert b"DTSTART:20261023T120000Z\r\n" in raw
    assert b"DTEND:20261023T130000Z\r\n" in raw
    exported, = components(raw)
    assert exported.decoded("LAST-MODIFIED") == NOW - timedelta(days=1)
    assert exported.decoded("DTSTAMP") == NOW - timedelta(days=1)


async def test_uid_stays_stable_on_edit_but_distinguishes_sources_and_occurrences(setup_db):
    a = await source(setup_db, provider="ical")
    b = await source(setup_db, provider="ical")
    row = await event(setup_db, a, "Original", external_uid="series")
    await event(setup_db, a, "Occurrence", external_uid="series_2026-10-24")
    await event(setup_db, b, "Other source", external_uid="series")
    before = {str(e["SUMMARY"]): e for e in components(await subscriptions.render_ics(setup_db, "family", "full"))}
    assert len({str(e["UID"]) for e in before.values()}) == 3
    row.title, row.start_dt, row.end_dt, row.updated_at = "Changed", NOW + timedelta(hours=2), NOW + timedelta(hours=3), NOW
    await setup_db.flush()
    after = {str(e["SUMMARY"]): e for e in components(await subscriptions.render_ics(setup_db, "family", "full"))}
    assert after["Changed"]["UID"] == before["Original"]["UID"]
    assert after["Changed"].decoded("LAST-MODIFIED") > before["Original"].decoded("LAST-MODIFIED")
    row.is_deleted = True
    await setup_db.flush()
    assert len(components(await subscriptions.render_ics(setup_db, "family", "full"))) == 2
    row.is_deleted = False
    await setup_db.flush()
    restored = {str(e["SUMMARY"]): e for e in components(await subscriptions.render_ics(setup_db, "family", "full"))}
    assert restored["Changed"]["UID"] == before["Original"]["UID"]


async def test_escaping_does_not_inject_properties_or_components(setup_db):
    src = await source(setup_db)
    title = 'Dinner, family; \\ café\nATTENDEE:mailto:injected@example.com'
    detail = 'Line one\nEND:VEVENT\nBEGIN:VEVENT\nSUMMARY:Injected'
    await event(setup_db, src, title, description=detail, location="Room; A, B",
                organizer='Office\r\nATTENDEE:mailto:injected@example.com',
                attendees=['A; B, "C"\nORGANIZER:mailto:injected@example.com'])
    exported, = components(await subscriptions.render_ics(setup_db, "family", "full"))
    assert str(exported["SUMMARY"]) == title
    assert str(exported["DESCRIPTION"]) == detail
    assert str(exported["LOCATION"]) == "Room; A, B"
    assert not isinstance(exported["ATTENDEE"], list)


async def test_participant_names_preserve_quotes_and_carets_using_rfc6868(setup_db):
    src = await source(setup_db)
    await event(setup_db, src, organizer='School "office" ^ reception', attendees=['Pat^nSmith'])
    exported, = components(await subscriptions.render_ics(setup_db, "family", "full"))
    # icalendar 5 doesn't decode RFC 6868 parameters. Assert wire values:
    # ^' represents a double quote, ^^ a literal caret (not a newline escape).
    assert str(exported["ORGANIZER"].params["CN"]) == "School ^'office^' ^^ reception"
    assert str(exported["ATTENDEE"].params["CN"]) == "Pat^^nSmith"


async def test_empty_family_produces_a_valid_calendar_without_generated_entries(setup_db):
    raw = await subscriptions.render_ics(setup_db, "family", "titles")
    cal = Calendar.from_ical(raw)
    assert str(cal["VERSION"]) == "2.0"
    assert str(cal["PRODID"]) and str(cal["X-WR-CALNAME"])
    assert components(raw) == []


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://event.example/\r\nATTENDEE:mailto:injected@example.com"])
async def test_unsafe_stored_urls_are_not_exported_or_allowed_to_break_snapshot(setup_db, url):
    src = await source(setup_db)
    await event(setup_db, src, url=url)
    exported, = components(await subscriptions.render_ics(setup_db, "family", "full"))
    assert "URL" not in exported
    assert "ATTENDEE" not in exported


async def test_invalid_kind_does_not_fall_through_to_full_details(setup_db):
    with pytest.raises(ValueError, match="kind"):
        await subscriptions.render_ics(setup_db, "family", "invalid")


async def test_relay_feed_is_encrypted_at_rest_and_can_be_revealed(setup_db):
    row = CalendarSubscription(family_id="family", kind="titles")
    subscriptions.set_relay_feed(row, RelayFeed("safe-feed-id", SECRET_URL))
    setup_db.add(row)
    await setup_db.flush()
    stored = (await setup_db.execute(text("SELECT relay_url_encrypted FROM calendar_subscriptions"))).scalar_one()
    assert SECRET_URL not in stored and "s" * 43 not in stored
    assert server_config._fernet().decrypt(stored.encode()).decode() == SECRET_URL
    assert subscriptions.decrypt_relay_url(stored) == SECRET_URL
    assert row.relay_id == "safe-feed-id"
    assert row.created_at.tzinfo == UTC and row.updated_at.tzinfo == UTC
    assert row.last_published_at is None and row.last_error is None
    assert row.active is False and row.publication_pending is False


@pytest.mark.parametrize("failure", ["changed-key", "corrupt", "empty", "missing"])
def test_unreadable_url_fails_safely_without_secret_in_error(monkeypatch, failure):
    token = subscriptions.encrypt_relay_url(SECRET_URL)
    if failure == "changed-key":
        monkeypatch.setattr(settings, "secret_key", "different-key")
    elif failure == "missing":
        token = None
    else:
        token = "corrupt" if failure == "corrupt" else ""
    with pytest.raises(ValueError) as caught:
        subscriptions.decrypt_relay_url(token)
    assert "could not be read" in str(caught.value)
    assert SECRET_URL not in str(caught.value)
    if token:
        assert token not in str(caught.value)


async def test_only_one_subscription_per_family_and_kind_with_independent_kinds(setup_db):
    setup_db.add_all([
        CalendarSubscription(family_id="family", kind="titles"),
        CalendarSubscription(family_id="family", kind="full"),
        CalendarSubscription(family_id="other", kind="titles"),
    ])
    await setup_db.flush()
    with pytest.raises(IntegrityError):
        async with setup_db.begin_nested():
            setup_db.add(CalendarSubscription(family_id="family", kind="titles"))
            await setup_db.flush()


@pytest.mark.parametrize("model,values", [
    (CalendarSubscription, {"kind": "other"}),
    (CalendarSubscriptionAudit, {"action": "other", "subscription_id": "feed", "actor_user_id": "actor"}),
])
async def test_database_rejects_unknown_kinds_and_audit_actions(setup_db, model, values):
    with pytest.raises(IntegrityError):
        async with setup_db.begin_nested():
            setup_db.add(model(family_id="family", **values))
            await setup_db.flush()


async def test_audits_persist_actor_action_and_utc_time_without_url_or_token_fields(setup_db):
    for action in ("created", "revealed", "rotated", "revoked"):
        setup_db.add(CalendarSubscriptionAudit(family_id="family", subscription_id="feed", action=action, actor_user_id="admin"))
    await setup_db.flush()
    rows = (await setup_db.execute(select(CalendarSubscriptionAudit))).scalars().all()
    assert {r.action for r in rows} == {"created", "revealed", "rotated", "revoked"}
    assert all(r.actor_user_id == "admin" and r.created_at.tzinfo == UTC for r in rows)
    assert set(CalendarSubscriptionAudit.__table__.columns.keys()) == {"id", "subscription_id", "family_id", "action", "actor_user_id", "created_at"}


def test_migration_upgrades_existing_database_and_downgrades_cleanly(tmp_path):
    db = tmp_path / "migration.db"
    env = {**os.environ, "SECRET_KEY": "migration-test-secret", "DATABASE_URL": f"sqlite+aiosqlite:///{db}"}

    def migrate(*args):
        proc = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env, text=True, capture_output=True)
        assert proc.returncode == 0, proc.stderr

    migrate("upgrade", "f3c4d5e6f015")
    with closing(sqlite3.connect(db)) as con, con:
        con.execute("INSERT INTO families (id, name, timezone, settings_json, is_deleted) VALUES ('family', 'Family', 'UTC', '{}', 0)")
    migrate("upgrade", "head")
    with closing(sqlite3.connect(db)) as con, con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"calendar_subscriptions", "calendar_subscription_audits"} <= tables
        assert con.execute("SELECT name FROM families").fetchone() == ("Family",)
        con.execute("INSERT INTO calendar_subscriptions (id, family_id, kind) VALUES ('t', 'family', 'titles')")
        con.execute("INSERT INTO calendar_subscriptions (id, family_id, kind) VALUES ('f', 'family', 'full')")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO calendar_subscriptions (id, family_id, kind) VALUES ('dup', 'family', 'titles')")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO calendar_subscriptions (id, family_id, kind) VALUES ('bad', 'family', 'other')")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO calendar_subscription_audits (id, subscription_id, family_id, action, actor_user_id) VALUES ('bad', 't', 'family', 'other', 'admin')")
    migrate("downgrade", "f3c4d5e6f015")
    with closing(sqlite3.connect(db)) as con, con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "calendar_subscriptions" not in tables and "calendar_subscription_audits" not in tables
        assert con.execute("SELECT name FROM families").fetchone() == ("Family",)
