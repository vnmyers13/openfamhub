import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.events import publish_queued, queue_event
from app.integrations.ical_feed import WINDOW_PAST, fetch_and_parse
from app.models.calendar_event import CalendarEvent
from app.models.family import Family
from app.models.calendar_source import CalendarSource
from app.models.calendar_sync_log import SyncLog


def describe_sync_error(exc: Exception) -> str:
    """A message an admin can act on (some httpx errors stringify to "")."""
    if isinstance(exc, httpx.TimeoutException):
        return "The calendar URL timed out"
    if isinstance(exc, httpx.RequestError):
        return f"Could not reach the calendar URL: {exc}" if str(exc) else "Could not reach the calendar URL"
    return str(exc) or exc.__class__.__name__


async def sync_source(source: CalendarSource, db: AsyncSession) -> str | None:
    """Fetch and store one iCal source. Errors are recorded on the source and
    in its sync log; the message is also returned (None on success)."""
    start_ms = int(time.time() * 1000)
    upserted = 0
    deleted = 0
    error_msg = None
    now = datetime.now(timezone.utc)

    try:
        family = await db.get(Family, source.family_id)
        parsed = await fetch_and_parse(
            source.ics_url, family_tz=family.timezone if family else None, now=now
        )
        # A feed can repeat a UID; the last copy wins.
        incoming = {event_data["external_uid"]: event_data for event_data in parsed}

        # One query for every synced row of this source (deleted ones too, so
        # an event that comes back is restored under its old id).
        result = await db.execute(
            select(CalendarEvent).where(
                CalendarEvent.source_id == source.id,
                CalendarEvent.external_uid.isnot(None),
            )
        )
        existing = {ev.external_uid: ev for ev in result.scalars().all()}

        for uid, event_data in incoming.items():
            ev = existing.get(uid)
            if ev is None:
                ev = CalendarEvent(source_id=source.id, family_id=source.family_id, external_uid=uid)
                db.add(ev)
            ev.title = event_data["title"]
            ev.start_dt = event_data["start_dt"]
            ev.end_dt = event_data["end_dt"]
            ev.all_day = event_data["all_day"]
            ev.location = event_data["location"]
            ev.description = event_data["description"]
            ev.url = event_data.get("url")
            ev.organizer = event_data.get("organizer")
            ev.attendees = event_data.get("attendees")
            ev.is_deleted = False
            upserted += 1

        # Gone from the feed. A successful sync of an empty feed means every
        # event is gone, so this runs even when nothing came in. Rows that have
        # left the storage window are deleted outright rather than kept as
        # soft-deleted history; the rest are hidden and restored if they return.
        window_start = now - WINDOW_PAST
        for uid, ev in existing.items():
            if uid in incoming:
                continue
            if ev.end_dt <= window_start:
                await db.delete(ev)
                deleted += 1
            elif not ev.is_deleted:
                ev.is_deleted = True
                deleted += 1

        source.last_synced_at = now
        source.sync_error = None
        await db.flush()

    except Exception as exc:
        error_msg = describe_sync_error(exc)
        source.sync_error = error_msg
        await db.flush()

    duration_ms = int(time.time() * 1000) - start_ms
    log = SyncLog(
        source_id=source.id,
        events_upserted=upserted,
        events_deleted=deleted,
        duration_ms=duration_ms,
        error=error_msg,
    )
    db.add(log)
    await db.flush()

    # Tell paired walls to re-fetch. Queued, so it is published only after the
    # caller commits (get_db for API requests, sync_all_due for the scheduler).
    queue_event(db, "calendar_updated", {"source_id": source.id})
    return error_msg


async def sync_all_due() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CalendarSource).where(
                CalendarSource.provider == "ical",
                CalendarSource.enabled == True,
                CalendarSource.is_deleted == False,
                CalendarSource.ics_url.isnot(None),
            )
        )
        sources = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        for source in sources:
            if source.last_synced_at is None:
                await sync_source(source, db)
            else:
                elapsed = (now - source.last_synced_at).total_seconds() / 3600
                if elapsed >= source.sync_interval_hours:
                    await sync_source(source, db)

        await db.commit()
        await publish_queued(db)


def register_sync_jobs(scheduler):
    scheduler.add_job(sync_all_due, "interval", minutes=15, id="calendar_sync_all_due", replace_existing=True)
