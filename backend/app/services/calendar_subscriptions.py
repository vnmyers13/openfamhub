"""Private relay URL storage and deterministic, stored-event-only ICS snapshots.

The publication horizon matches iCal ingestion: 90 days back, 365 days ahead,
using strict overlap. Computed birthdays and other non-event data aren't feeds.
Publication never fetches source URLs; only the background coordinator sends
stored-event snapshots to the relay.
"""
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from cryptography.fernet import InvalidToken
from icalendar import Calendar, Event, vCalAddress, vText
from sqlalchemy import String, cast, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.calendar_relay import RelayFeed
from app.integrations import calendar_relay
from app.integrations.ical_feed import WINDOW_FUTURE, WINDOW_PAST
from app.models.calendar_event import CalendarEvent
from app.models.calendar_source import CalendarSource
from app.models.calendar_subscription import CalendarSubscription
from app.services import server_config

RETRY_INTERVAL = timedelta(seconds=60)


def publication_due_conditions() -> tuple:
    """Shared selection/last-minute gate, using durable state, not process flags.

    A validated effective URL/token change is the operator's repair signal,
    including an environment change followed by restart. Unrelated settings,
    calendar edits, restarts, and absent/invalid configuration cannot unpause.
    """
    pause_ready = CalendarSubscription.auth_paused_config.is_(None)
    try:
        identity = calendar_relay.configuration_identity()
    except calendar_relay.RelayUnavailable:
        pass
    else:
        pause_ready = or_(pause_ready, CalendarSubscription.auth_paused_config != identity)
    return (
        CalendarSubscription.active == True,
        CalendarSubscription.publication_pending == True,
        pause_ready,
        or_(CalendarSubscription.next_attempt_at.is_(None),
            CalendarSubscription.next_attempt_at <= datetime.now(timezone.utc)),
    )


async def mark_family_subscriptions_dirty(db: AsyncSession, family_id: str) -> None:
    """Durable outbox marker, committed/rolled back with the calendar mutation.

    Advance the generation even if already pending: a delivery in flight must
    not acknowledge a newer change. No network I/O or transaction commit here.
    """
    rows = (await db.execute(select(CalendarSubscription).where(
        CalendarSubscription.family_id == family_id,
        CalendarSubscription.active == True,
    ))).scalars().all()
    now = datetime.now(timezone.utc)
    for row in rows:
        row.publication_pending = True
        row.updated_at = max(now, row.updated_at + timedelta(microseconds=1))
    await db.flush()


async def publish_subscription(db: AsyncSession, subscription: CalendarSubscription) -> None:
    """Deliver one committed pending feed from a fresh background session.

    The coordinator owns this session, never a request's uncommitted changes.
    Keep the durable marker until success; a crash after sending simply retries
    the same full replacement. A compare-and-set preserves edits during I/O.
    """
    subscription = (await db.execute(select(CalendarSubscription).where(
        CalendarSubscription.id == subscription.id,
        CalendarSubscription.family_id == subscription.family_id,
        *publication_due_conditions(),
    ).execution_options(populate_existing=True))).scalar_one_or_none()
    if subscription is None:
        return
    subscription_id, family_id = subscription.id, subscription.family_id
    generation, relay_id = subscription.updated_at, subscription.relay_id
    try:
        raw = await render_ics(db, family_id, subscription.kind)
        # End the snapshot's read transaction before waiting for the network.
        await db.commit()
        await calendar_relay.replace_feed(relay_id, raw)
    except calendar_relay.RelayAuthenticationRejected as exc:
        values = {
            "auth_paused_config": exc.configuration_identity,
            "next_attempt_at": None,
            "last_error": "Calendar relay authentication failed; repair the relay configuration",
        }
    except Exception:
        # Never persist/log provider exceptions (URLs or credentials may occur).
        values = {
            "last_error": "Could not reach the calendar relay",
            "auth_paused_config": None,
            "next_attempt_at": datetime.now(timezone.utc) + RETRY_INTERVAL,
        }
    else:
        values = {
            "publication_pending": False,
            "last_published_at": datetime.now(timezone.utc),
            "last_error": None,
            "auth_paused_config": None,
            "next_attempt_at": None,
        }
    # Avoid SQLite's second-resolution func.now(): it also writes a different
    # text representation from UTCDateTime, which would break the next CAS.
    succeeded = "publication_pending" in values
    # Failures must persist pause/backoff even if an edit happened during I/O,
    # without overwriting that edit's dirty generation or clearing its marker.
    values["updated_at"] = (max(datetime.now(timezone.utc), generation + timedelta(microseconds=1))
                            if succeeded else CalendarSubscription.updated_at)
    same_generation = CalendarSubscription.updated_at == generation
    if generation.microsecond == 0:
        # Lifecycle writes may still use the model's CURRENT_TIMESTAMP default.
        # Match its exact second-only spelling too, without dropping precision
        # from dirty markers (which distinguish changes within the same second).
        same_generation = or_(same_generation, cast(CalendarSubscription.updated_at, String) ==
                              generation.strftime("%Y-%m-%d %H:%M:%S"))
    await db.execute(update(CalendarSubscription).where(
        CalendarSubscription.id == subscription_id,
        CalendarSubscription.family_id == family_id,
        CalendarSubscription.relay_id == relay_id,
        CalendarSubscription.active == True,
        CalendarSubscription.publication_pending == True,
        same_generation if succeeded else True,
    ).values(**values).execution_options(synchronize_session=False))
    await db.flush()


def encrypt_relay_url(url: str) -> str:
    """Use exactly the server-settings HKDF/Fernet derivation from SECRET_KEY."""
    return server_config._fernet().encrypt(url.encode()).decode()


def decrypt_relay_url(ciphertext: str | None) -> str:
    """Fail closed on corruption/key changes without including secret material."""
    try:
        if not isinstance(ciphertext, str):
            raise ValueError
        return server_config._fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError, UnicodeError):
        raise ValueError("calendar subscription URL could not be read; create a replacement") from None


def set_relay_feed(subscription: CalendarSubscription, feed: RelayFeed) -> None:
    """Keep validated relay identity and ciphertext only; activation is separate."""
    ciphertext = encrypt_relay_url(feed.subscription_url)
    subscription.relay_id = feed.relay_id
    subscription.relay_url_encrypted = ciphertext


def _participant(value: str) -> vCalAddress:
    # Stored names lack the original CAL-ADDRESS. Preserve the name in CN and
    # use a stable non-routable URI instead of inventing an email address.
    # icalendar 5 doesn't escape CR/LF in parameter values; remove controls.
    name = re.sub(r"[\x00-\x1f\x7f]+", " ", value).strip()
    address = name[7:] if name.lower().startswith("mailto:") else name
    if re.fullmatch(r"[^\s@<>,;:\"\\]+@[^\s@<>,;:\"\\]+", address):
        uri = "mailto:" + address
    else:
        uri = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "openfamhub participant:" + name))
    participant = vCalAddress(uri)
    # RFC 6868: icalendar 5 otherwise changes double quotes to apostrophes,
    # and literal carets must not be mistaken for a client's escape sequence.
    participant.params["CN"] = vText(name.replace("^", "^^").replace('"', "^'"))
    return participant


async def render_ics(db: AsyncSession, family_id: str, kind: Literal["titles", "full"]) -> bytes:
    if kind not in ("titles", "full"):
        raise ValueError("calendar subscription kind must be titles or full")
    now = datetime.now(timezone.utc)
    rows = (await db.execute(
        select(CalendarEvent)
        .join(CalendarSource, CalendarEvent.source_id == CalendarSource.id)
        .where(
            CalendarSource.family_id == family_id,
            CalendarEvent.family_id == family_id,
            CalendarSource.is_deleted == False,
            CalendarSource.enabled == True,
            CalendarEvent.is_deleted == False,
            CalendarEvent.start_dt < now + WINDOW_FUTURE,
            CalendarEvent.end_dt > now - WINDOW_PAST,
        )
        .order_by(CalendarEvent.start_dt, CalendarEvent.source_id, CalendarEvent.id)
    )).scalars().all()

    calendar = Calendar()
    calendar.add("prodid", "-//OpenFamHub//Calendar subscriptions//EN")
    calendar.add("version", "2.0")
    calendar.add("x-wr-calname", "OpenFamHub")
    for row in rows:
        component = Event()
        # Hash the local normalized identity: never disclose an upstream UID,
        # source URL, family/user ID, or host address in the public feed.
        identity = json.dumps([row.family_id, row.source_id, row.id])
        component.add("uid", str(uuid.uuid5(uuid.NAMESPACE_URL, "openfamhub event:" + identity)) + "@openfamhub")
        component.add("summary", row.title)
        start, end = row.start_dt.astimezone(timezone.utc), row.end_dt.astimezone(timezone.utc)
        component.add("dtstart", start.date() if row.all_day else start)
        component.add("dtend", end.date() if row.all_day else end)
        # No persisted SEQUENCE exists. LAST-MODIFIED is the stored revision;
        # DTSTAMP must not be publication time (unchanged snapshots are stable).
        modified = row.updated_at.astimezone(timezone.utc)
        component.add("dtstamp", modified)
        component.add("last-modified", modified)
        if kind == "full":
            for field in ("description", "location"):
                value = getattr(row, field)
                if value:
                    component.add(field, value)
            # URI properties aren't TEXT-escaped by icalendar. Do not let an
            # invalid legacy URL break the entire snapshot or inject content.
            if (row.url and row.url.lower().startswith(("http://", "https://"))
                    and not re.search(r"[\x00-\x20\x7f]", row.url)):
                component.add("url", row.url)
            if row.organizer:
                component.add("organizer", _participant(row.organizer), encode=0)
            for attendee in row.attendees or []:
                component.add("attendee", _participant(attendee), encode=0)
        calendar.add_component(component)
    return calendar.to_ical()
