from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.calendar_event import CalendarEvent
from app.models.calendar_source import CalendarSource
from app.models.user import User
from app.schemas.calendar import (
    CalendarEventResponse,
    CalendarSourceResponse,
    CreateCalendarSourceRequest,
    CreateEventRequest,
    PatchCalendarSourceRequest,
    PatchEventRequest,
    SyncLogResponse,
)
from app.services.calendar import get_events_in_range, get_or_create_internal_source, get_source_logs
from app.jobs.calendar_sync import sync_source as run_source_sync
from app.routers.ws import event_bus

router = APIRouter()


def _parse_dt(value: str, field: str) -> datetime:
    """Parse an ISO8601 value; naive values are taken as UTC."""
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime for {field}")
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _check_can_edit(user: User, event: CalendarEvent, provider: str) -> None:
    """Who may change an event:
    - nobody edits events from a calendar subscription (the next sync would undo it)
    - viewers are read-only
    - members change only events they created
    - admins change any family event (no password step needed: everyday family use)
    """
    if provider != "internal":
        raise HTTPException(status_code=403, detail="Events from a subscribed calendar are read-only")
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers can't change events")
    if user.role != "admin" and event.created_by != user.id:
        raise HTTPException(status_code=403, detail="You can only change events you created")


def _build_event_response(event: CalendarEvent, color_hex: str) -> CalendarEventResponse:
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
        created_at=event.created_at.isoformat() if event.created_at else None,
        updated_at=event.updated_at.isoformat() if event.updated_at else None,
    )


@router.get("/events", response_model=List[CalendarEventResponse])
async def list_events(
    start: str = Query(..., description="ISO8601 start datetime"),
    end: str = Query(..., description="ISO8601 end datetime"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_dt = _parse_dt(start, "start")
    end_dt = _parse_dt(end, "end")
    return await get_events_in_range(db, current_user.family_id, start_dt, end_dt)


@router.post("/events", response_model=CalendarEventResponse, status_code=201)
async def create_event(
    data: CreateEventRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers can't add events")
    start_dt = _parse_dt(data.start_dt, "start_dt")
    end_dt = _parse_dt(data.end_dt, "end_dt")
    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="end_dt must be after start_dt")
    source = await get_or_create_internal_source(db, current_user.family_id)
    event = CalendarEvent(
        source_id=source.id,
        family_id=current_user.family_id,
        title=data.title,
        start_dt=start_dt,
        end_dt=end_dt,
        all_day=data.all_day,
        location=data.location,
        description=data.description,
        created_by=current_user.id,
    )
    db.add(event)
    await db.flush()
    await event_bus.emit("calendar_updated", {"source_id": source.id})
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
        source_color_hex=source.color_hex,
        created_at=event.created_at.isoformat() if event.created_at else None,
        updated_at=event.updated_at.isoformat() if event.updated_at else None,
    )


@router.get("/events/{event_id}", response_model=CalendarEventResponse)
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event, color_hex, _ = await _load_event_with_source(db, event_id, current_user.family_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return _build_event_response(event, color_hex)


@router.patch("/events/{event_id}", response_model=CalendarEventResponse)
async def update_event(
    event_id: str,
    data: PatchEventRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Load through the family-scoped join first, so an ID from another family
    # is a 404 and nothing is written before the permission check.
    event, color_hex, provider = await _load_event_with_source(db, event_id, current_user.family_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _check_can_edit(current_user, event, provider)

    if data.title is not None:
        event.title = data.title
    if data.start_dt is not None:
        event.start_dt = _parse_dt(data.start_dt, "start_dt")
    if data.end_dt is not None:
        event.end_dt = _parse_dt(data.end_dt, "end_dt")
    if data.all_day is not None:
        event.all_day = data.all_day
    if data.location is not None:
        event.location = data.location
    if data.description is not None:
        event.description = data.description
    if event.end_dt <= event.start_dt:
        raise HTTPException(status_code=400, detail="end_dt must be after start_dt")
    await db.flush()
    await event_bus.emit("calendar_updated", {"source_id": event.source_id})
    return _build_event_response(event, color_hex)


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event, _, provider = await _load_event_with_source(db, event_id, current_user.family_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _check_can_edit(current_user, event, provider)
    event.is_deleted = True
    await db.flush()
    await event_bus.emit("calendar_updated", {"source_id": event.source_id})
    return {"ok": True}


@router.get("/sources", response_model=List[CalendarSourceResponse])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CalendarSource).where(
            CalendarSource.family_id == current_user.family_id,
            CalendarSource.is_deleted == False,
        )
    )
    return list(result.scalars().all())


@router.post("/sources", response_model=CalendarSourceResponse, status_code=201)
async def create_source(
    data: CreateCalendarSourceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    source = CalendarSource(
        family_id=current_user.family_id,
        provider=data.provider,
        display_name=data.display_name,
        color_hex=data.color_hex,
        ics_url=data.ics_url,
        sync_interval_hours=data.sync_interval_hours,
    )
    db.add(source)
    await db.flush()
    return source


@router.patch("/sources/{source_id}", response_model=CalendarSourceResponse)
async def update_source(
    source_id: str,
    data: PatchCalendarSourceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(CalendarSource).where(
            CalendarSource.id == source_id,
            CalendarSource.family_id == current_user.family_id,
            CalendarSource.is_deleted == False,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    updates = {}
    if data.display_name is not None:
        updates["display_name"] = data.display_name
    if data.color_hex is not None:
        updates["color_hex"] = data.color_hex
    if data.ics_url is not None:
        updates["ics_url"] = data.ics_url
    if data.sync_interval_hours is not None:
        updates["sync_interval_hours"] = data.sync_interval_hours
    if data.enabled is not None:
        updates["enabled"] = data.enabled
    if updates:
        for k, v in updates.items():
            setattr(source, k, v)
        await db.flush()
    return source


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(CalendarSource).where(
            CalendarSource.id == source_id,
            CalendarSource.family_id == current_user.family_id,
            CalendarSource.is_deleted == False,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.provider == "internal":
        raise HTTPException(status_code=400, detail="The family calendar can't be deleted")
    source.enabled = False
    source.is_deleted = True
    await db.flush()
    await event_bus.emit("calendar_updated", {"source_id": source.id})
    return {"ok": True}


@router.post("/sources/{source_id}/sync")
async def sync_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(CalendarSource).where(
            CalendarSource.id == source_id,
            CalendarSource.family_id == current_user.family_id,
            CalendarSource.is_deleted == False,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.provider != "ical" or not source.ics_url:
        raise HTTPException(status_code=400, detail="Only iCal sources can be synced")
    # sync_source records its own errors on the source and in the sync log.
    await run_source_sync(source, db)
    await event_bus.emit("calendar_updated", {"source_id": source.id})
    return {"ok": source.sync_error is None, "error": source.sync_error}


@router.get("/sources/{source_id}/log", response_model=List[SyncLogResponse])
async def source_logs(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CalendarSource).where(
            CalendarSource.id == source_id,
            CalendarSource.family_id == current_user.family_id,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return await get_source_logs(db, source_id)


async def _load_event_with_source(
    db: AsyncSession, event_id: str, family_id: str
):
    result = await db.execute(
        select(CalendarEvent, CalendarSource.color_hex, CalendarSource.provider)
        .join(CalendarSource, CalendarEvent.source_id == CalendarSource.id)
        .where(
            CalendarEvent.id == event_id,
            CalendarEvent.is_deleted == False,
            CalendarSource.family_id == family_id,
        )
    )
    row = result.one_or_none()
    if not row:
        return None, None, None
    return row[0], row[1], row[2]
