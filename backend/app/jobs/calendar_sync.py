import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.integrations.ical_feed import fetch_and_parse
from app.models.calendar_event import CalendarEvent
from app.models.calendar_source import CalendarSource
from app.models.calendar_sync_log import SyncLog


async def sync_source(source: CalendarSource, db: AsyncSession) -> None:
    start_ms = int(time.time() * 1000)
    upserted = 0
    deleted = 0
    error_msg = None

    try:
        parsed = await fetch_and_parse(source.ics_url)

        incoming_uids = set()
        for event_data in parsed:
            incoming_uids.add(event_data["external_uid"])

            existing = await db.execute(
                select(CalendarEvent).where(
                    CalendarEvent.source_id == source.id,
                    CalendarEvent.external_uid == event_data["external_uid"],
                )
            )
            ev = existing.scalar_one_or_none()

            if ev:
                ev.title = event_data["title"]
                ev.start_dt = event_data["start_dt"]
                ev.end_dt = event_data["end_dt"]
                ev.all_day = event_data["all_day"]
                ev.location = event_data["location"]
                ev.description = event_data["description"]
                ev.is_deleted = False
            else:
                ev = CalendarEvent(
                    source_id=source.id,
                    family_id=source.family_id,
                    external_uid=event_data["external_uid"],
                    title=event_data["title"],
                    start_dt=event_data["start_dt"],
                    end_dt=event_data["end_dt"],
                    all_day=event_data["all_day"],
                    location=event_data["location"],
                    description=event_data["description"],
                )
                db.add(ev)
            upserted += 1

        if incoming_uids:
            result = await db.execute(
                select(CalendarEvent).where(
                    CalendarEvent.source_id == source.id,
                    CalendarEvent.external_uid.isnot(None),
                    CalendarEvent.external_uid.notin_(incoming_uids),
                )
            )
            stale = list(result.scalars().all())
            for s in stale:
                s.is_deleted = True
                deleted += 1

        source.last_synced_at = datetime.now(timezone.utc)
        source.sync_error = None
        await db.flush()

    except Exception as exc:
        error_msg = str(exc)
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


def register_sync_jobs(scheduler):
    scheduler.add_job(sync_all_due, "interval", minutes=15, id="calendar_sync_all_due", replace_existing=True)
