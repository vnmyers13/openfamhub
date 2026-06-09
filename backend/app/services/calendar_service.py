from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.models.event import CalendarSource, CalendarEvent, SyncLog
from app.integrations.ical_feed import fetch_ics_feed, parse_calendar_events


async def sync_calendar_source(db: AsyncSession, source: CalendarSource) -> SyncLog:
    """Sync a calendar source from its ICS URL."""
    from datetime import datetime, timezone

    sync_log = SyncLog(
        id=str(__import__('uuid').uuid4()),
        source_id=source.id,
        events_imported=0,
        events_deleted=0,
        errors="[]",
        started_at=datetime.now(timezone.utc).isoformat(),
        status="success",
    )
    db.add(sync_log)
    await db.flush()

    cal = await fetch_ics_feed(source.url)
    if cal is None:
        sync_log.status = "error"
        sync_log.errors = '[\"Failed to fetch ICS feed\"]'
        sync_log.completed_at = datetime.now(timezone.utc).isoformat()
        return sync_log

    new_events = parse_calendar_events(cal, source.id, source.color_hex)
    sync_log.events_imported = len(new_events)

    # Delete old events from this source
    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.source_id == source.id)
    )
    old_events = result.scalars().all()
    for event in old_events:
        event.is_deleted = True

    # Insert new events
    for event_data in new_events:
        db.add(CalendarEvent(**event_data))

    source.last_synced_at = datetime.now(timezone.utc).isoformat()
    sync_log.completed_at = datetime.now(timezone.utc).isoformat()

    return sync_log
