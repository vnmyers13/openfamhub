from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar_source import CalendarSource
from app.models.calendar_event import CalendarEvent
from app.models.calendar_sync_log import SyncLog


async def get_or_create_internal_source(db: AsyncSession, family_id: str) -> CalendarSource:
    result = await db.execute(
        select(CalendarSource).where(
            CalendarSource.family_id == family_id,
            CalendarSource.provider == "internal",
            CalendarSource.is_deleted == False,
        )
    )
    source = result.scalar_one_or_none()
    if source:
        return source
    source = CalendarSource(
        family_id=family_id,
        provider="internal",
        display_name="Family Calendar",
        color_hex="#4F46E5",
    )
    db.add(source)
    await db.flush()
    return source


async def get_events_in_range(
    db: AsyncSession, family_id: str, start: datetime, end: datetime
) -> list[dict]:
    result = await db.execute(
        select(
            CalendarEvent,
            CalendarSource.color_hex,
            CalendarSource.display_name,
        )
        .join(CalendarSource, CalendarEvent.source_id == CalendarSource.id)
        .where(
            CalendarSource.family_id == family_id,
            CalendarEvent.is_deleted == False,
            CalendarEvent.start_dt >= start,
            CalendarEvent.start_dt <= end,
        )
        .order_by(CalendarEvent.start_dt)
    )
    rows = result.all()
    events = []
    for event, color_hex, source_name in rows:
        d = {
            "id": event.id,
            "source_id": event.source_id,
            "family_id": event.family_id,
            "external_uid": event.external_uid,
            "title": event.title,
            "start_dt": event.start_dt.isoformat() if event.start_dt else None,
            "end_dt": event.end_dt.isoformat() if event.end_dt else None,
            "all_day": event.all_day,
            "location": event.location,
            "description": event.description,
            "created_by": event.created_by,
            "is_deleted": event.is_deleted,
            "source_color_hex": color_hex,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "updated_at": event.updated_at.isoformat() if event.updated_at else None,
        }
        events.append(d)
    return events


async def get_source_logs(db: AsyncSession, source_id: str, limit: int = 20) -> list[SyncLog]:
    result = await db.execute(
        select(SyncLog)
        .where(SyncLog.source_id == source_id)
        .order_by(SyncLog.synced_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
