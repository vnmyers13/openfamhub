"""Phase 3: the sync job (family timezone, one UID lookup per sync, window pruning)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, select

from app.integrations.ical_feed import WINDOW_PAST
from app.models.calendar_event import CalendarEvent
from tests.test_phase2 import SETUP, _cookie, _h
from tests.test_calendar_subscriptions import (
    active_feeds, feed_states, publication_db, relay_recorder, run_publication,
)


@pytest.fixture(autouse=True)
def _reset_throttle():
    from app.core.security import login_throttle

    login_throttle.reset()
    yield
    login_throttle.reset()


@pytest.fixture
async def admin(client):
    res = await client.post("/api/auth/setup", json=SETUP)
    assert res.status_code == 200, res.text
    return {"Cookie": _cookie(res), "id": res.json()["id"]}


def _ev(uid, start, hours=1, title=None):
    return {
        "external_uid": uid, "title": title or uid, "start_dt": start,
        "end_dt": start + timedelta(hours=hours), "all_day": False,
        "location": None, "description": None,
    }


class Feed:
    """Stands in for fetch_and_parse and records how it was called."""

    def __init__(self, events):
        self.events = events
        self.calls = []

    async def __call__(self, url, **kwargs):
        self.calls.append(kwargs)
        return list(self.events)


async def _source(client, admin):
    res = await client.post(
        "/api/calendar/sources",
        json={"display_name": "School", "ics_url": "https://example.test/s.ics"},
        headers=_h(admin),
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _sync(client, admin, source_id):
    res = await client.post(f"/api/calendar/sources/{source_id}/sync", headers=_h(admin))
    assert res.status_code == 200, res.text


async def _rows(db, source_id):
    result = await db.execute(select(CalendarEvent).where(CalendarEvent.source_id == source_id))
    return {e.external_uid: e for e in result.scalars().all()}


NOW = datetime.now(timezone.utc).replace(microsecond=0)


async def test_sync_reads_floating_times_in_the_family_timezone(client, admin, monkeypatch):
    feed = Feed([_ev("a", NOW)])
    monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", feed)
    await _sync(client, admin, await _source(client, admin))
    assert feed.calls[0]["family_tz"] == SETUP["timezone"]


async def test_sync_looks_up_existing_events_in_one_query(client, admin, setup_db, monkeypatch):
    feed = Feed([_ev(f"e{i}", NOW + timedelta(days=i)) for i in range(40)])
    monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", feed)
    source_id = await _source(client, admin)
    await _sync(client, admin, source_id)  # first sync inserts

    selects = []

    def count(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith("SELECT") and "calendar_events" in statement:
            selects.append(statement)

    engine = setup_db.bind.sync_engine
    event.listen(engine, "before_cursor_execute", count)
    try:
        await _sync(client, admin, source_id)  # second sync updates all 40
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert len(selects) == 1, selects


async def test_sync_updates_rows_in_place_and_restores_returning_events(client, admin, setup_db, monkeypatch):
    feed = Feed([_ev("a", NOW, title="Before"), _ev("b", NOW + timedelta(days=1))])
    monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", feed)
    source_id = await _source(client, admin)
    await _sync(client, admin, source_id)
    first = await _rows(setup_db, source_id)
    ids = {uid: e.id for uid, e in first.items()}

    feed.events = [_ev("a", NOW, title="After")]  # b disappears
    await _sync(client, admin, source_id)
    rows = await _rows(setup_db, source_id)
    assert rows["a"].id == ids["a"] and rows["a"].title == "After"
    assert rows["b"].is_deleted is True

    feed.events = [_ev("a", NOW, title="After"), _ev("b", NOW + timedelta(days=1))]  # b is back
    await _sync(client, admin, source_id)
    rows = await _rows(setup_db, source_id)
    assert rows["b"].id == ids["b"] and rows["b"].is_deleted is False


async def test_sync_drops_rows_that_left_the_window(client, admin, setup_db, monkeypatch):
    long_ago = NOW - WINDOW_PAST - timedelta(days=10)
    feed = Feed([_ev("old", long_ago), _ev("current", NOW)])
    monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", feed)
    source_id = await _source(client, admin)
    await _sync(client, admin, source_id)

    feed.events = [_ev("current", NOW)]  # the parser stops returning out-of-window events
    await _sync(client, admin, source_id)
    rows = await _rows(setup_db, source_id)
    assert "old" not in rows  # deleted outright, not kept as soft-deleted history
    assert rows["current"].is_deleted is False


async def test_duplicate_uids_in_a_feed_are_stored_once(client, admin, setup_db, monkeypatch):
    feed = Feed([_ev("dup", NOW, title="First"), _ev("dup", NOW, title="Second")])
    monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", feed)
    source_id = await _source(client, admin)
    await _sync(client, admin, source_id)
    rows = await _rows(setup_db, source_id)
    assert list(rows) == ["dup"]


ICS = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//t//EN\r\nBEGIN:VEVENT\r\nUID:first\r\n"
    f"DTSTART:{(NOW + timedelta(days=1)).strftime('%Y%m%dT%H%M%SZ')}\r\n"
    f"DTEND:{(NOW + timedelta(days=1, hours=1)).strftime('%Y%m%dT%H%M%SZ')}\r\n"
    "SUMMARY:First event\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
).encode()


class TestAddIcalSource:
    async def test_downloads_the_feed_once(self, client, admin, monkeypatch):
        calls = []

        async def fake_bytes(url, **kwargs):
            calls.append(url)
            return ICS

        monkeypatch.setattr("app.integrations.ical_feed.fetch_ics_bytes", fake_bytes)
        res = await client.post(
            "/api/integrations/ical",
            json={"display_name": "School", "ics_url": "https://example.test/s.ics"},
            headers=_h(admin),
        )
        assert res.status_code == 201, res.text
        assert calls == ["https://example.test/s.ics"]
        source = res.json()
        assert source["sync_error"] is None and source["last_synced_at"]
        events = (await client.get(
            "/api/calendar/events",
            params={"start": NOW.isoformat(), "end": (NOW + timedelta(days=3)).isoformat()},
            headers=_h(admin),
        )).json()
        assert [e["title"] for e in events] == ["First event"]

    async def test_a_failed_first_sync_is_a_400_and_saves_nothing(self, client, admin, setup_db, monkeypatch):
        async def broken(url, **kwargs):
            raise ValueError("ICS fetch returned HTTP 404")

        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", broken)
        res = await client.post(
            "/api/integrations/ical",
            json={"display_name": "Broken", "ics_url": "https://example.test/missing.ics"},
            headers=_h(admin),
        )
        assert res.status_code == 400
        assert "HTTP 404" in res.json()["detail"]
        sources = (await client.get("/api/calendar/sources", headers=_h(admin))).json()
        assert all(s["display_name"] != "Broken" for s in sources)

    async def test_an_unparseable_feed_is_rejected(self, client, admin, monkeypatch):
        async def not_ics(url, **kwargs):
            return b"<html>Sign in to continue</html>"

        monkeypatch.setattr("app.integrations.ical_feed.fetch_ics_bytes", not_ics)
        res = await client.post(
            "/api/integrations/ical",
            json={"display_name": "Login page", "ics_url": "https://example.test/login"},
            headers=_h(admin),
        )
        assert res.status_code == 400

    async def test_timeouts_are_described(self, client, admin, monkeypatch):
        import httpx

        async def slow(url, **kwargs):
            raise httpx.ReadTimeout("")

        monkeypatch.setattr("app.integrations.ical_feed.fetch_ics_bytes", slow)
        res = await client.post(
            "/api/integrations/ical",
            json={"display_name": "Slow", "ics_url": "https://example.test/slow.ics"},
            headers=_h(admin),
        )
        assert res.status_code == 400
        assert res.json()["detail"] == "The calendar URL timed out"


class TestScheduledSync:
    """sync_all_due: which sources the 15-minute job actually syncs."""

    async def test_only_due_enabled_feeds_are_synced(self, client, admin, setup_db, monkeypatch):
        from contextlib import asynccontextmanager

        from app.jobs import calendar_sync
        from app.models.calendar_source import CalendarSource

        urls = []

        async def recording(url, **kwargs):
            urls.append(url)
            return []

        @asynccontextmanager
        async def shared_session():
            yield setup_db

        monkeypatch.setattr(calendar_sync, "fetch_and_parse", recording)
        monkeypatch.setattr(calendar_sync, "AsyncSessionLocal", shared_session)

        now = datetime.now(timezone.utc)
        setup = {
            "never": {},
            "recent": {"last_synced_at": now - timedelta(hours=1)},   # interval is 6 h
            "overdue": {"last_synced_at": now - timedelta(hours=7)},
            "disabled": {"enabled": False},
        }
        for name, attrs in setup.items():
            source = await setup_db.get(CalendarSource, await _source(client, admin))
            source.ics_url = f"https://example.test/{name}.ics"
            for key, value in attrs.items():
                setattr(source, key, value)
        await setup_db.flush()

        await calendar_sync.sync_all_due()

        assert sorted(urls) == ["https://example.test/never.ics", "https://example.test/overdue.ics"]

    def test_job_runs_every_15_minutes(self):
        from app.jobs.calendar_sync import register_sync_jobs

        added = {}

        class FakeScheduler:
            def add_job(self, fn, trigger, **kw):
                added.update(trigger=trigger, **kw)

        register_sync_jobs(FakeScheduler())
        assert (added["trigger"], added["minutes"], added["id"]) == ("interval", 15, "calendar_sync_all_due")


@pytest.mark.parametrize("scheduled", [False, True])
@pytest.mark.parametrize("failed", [False, True])
async def test_only_successful_sync_dirties_committed_subscriptions(
    publication_db, relay_recorder, monkeypatch, scheduled, failed,
):
    from app.jobs import calendar_sync

    client, factory, headers, family_id = publication_db
    res = await client.post("/api/calendar/sources", headers=headers, json={
        "display_name": "School", "ics_url": "https://example.test/s.ics",
    })
    assert res.status_code == 201
    source_id = res.json()["id"]
    await active_feeds(factory, family_id)

    async def fetch(url, **kwargs):
        if failed:
            raise ValueError("Could not fetch school calendar")
        return [_ev("concert", NOW, title="School concert")]

    monkeypatch.setattr(calendar_sync, "fetch_and_parse", fetch)
    if scheduled:
        monkeypatch.setattr(calendar_sync, "AsyncSessionLocal", factory)
        await calendar_sync.sync_all_due()
    else:
        res = await client.post(f"/api/calendar/sources/{source_id}/sync", headers=headers)
        assert res.status_code == 200 and res.json()["ok"] is not failed
    assert all(row.publication_pending is not failed for row in (await feed_states(factory)).values())
    assert relay_recorder.documents == {}
    await run_publication(factory, monkeypatch)
    if failed:
        assert relay_recorder.documents == {}
    else:
        assert b"School concert" in relay_recorder.documents["full"]


async def test_failed_source_url_savepoint_does_not_dirty_subscriptions(publication_db, relay_recorder, monkeypatch):
    from app.jobs import calendar_sync

    client, factory, headers, family_id = publication_db
    res = await client.post("/api/calendar/sources", headers=headers, json={
        "display_name": "School", "ics_url": "https://example.test/old.ics",
    })
    source_id = res.json()["id"]
    await active_feeds(factory, family_id)

    async def broken(url, **kwargs):
        raise ValueError("Feed unavailable")

    monkeypatch.setattr(calendar_sync, "fetch_and_parse", broken)
    res = await client.patch(f"/api/calendar/sources/{source_id}", headers=headers, json={
        "ics_url": "https://example.test/new.ics", "display_name": "Not saved",
    })
    assert res.status_code == 400
    assert all(not row.publication_pending for row in (await feed_states(factory)).values())
    await run_publication(factory, monkeypatch)
    assert relay_recorder.documents == {}
