from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar_source import CalendarSource
from app.models.calendar_event import CalendarEvent
from app.models.calendar_sync_log import SyncLog
from app.schemas.calendar import CalendarEventResponse


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


def event_to_response(event: CalendarEvent, color_hex: str | None) -> CalendarEventResponse:
    """The single place an event becomes an API response."""
    return CalendarEventResponse(
        id=event.id,
        source_id=event.source_id,
        family_id=event.family_id,
        external_uid=event.external_uid,
        title=event.title,
        start_dt=event.start_dt.isoformat() if event.start_dt else "",
        end_dt=event.end_dt.isoformat() if event.end_dt else "",
        all_day=event.all_day,
        location=event.location,
        description=event.description,
        created_by=event.created_by,
        is_deleted=event.is_deleted,
        source_color_hex=color_hex,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


async def get_events_in_range(
    db: AsyncSession, family_id: str, start: datetime, end: datetime
) -> list[CalendarEventResponse]:
    result = await db.execute(
        select(
            CalendarEvent,
            CalendarSource.color_hex,
            CalendarSource.display_name,
        )
        .join(CalendarSource, CalendarEvent.source_id == CalendarSource.id)
        .where(
            CalendarSource.family_id == family_id,
            CalendarSource.is_deleted == False,
            CalendarSource.enabled == True,
            CalendarEvent.is_deleted == False,
            # Overlap, not containment: multi-day events that started before
            # the window (or end after it) must still be returned.
            CalendarEvent.start_dt < end,
            CalendarEvent.end_dt > start,
        )
        .order_by(CalendarEvent.start_dt)
    )
    return [event_to_response(event, color_hex) for event, color_hex, _name in result.all()]


async def get_source_logs(db: AsyncSession, source_id: str, limit: int = 20) -> list[SyncLog]:
    result = await db.execute(
        select(SyncLog)
        .where(SyncLog.source_id == source_id)
        .order_by(SyncLog.synced_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
