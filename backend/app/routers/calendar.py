from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update as sql_update
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

router = APIRouter()


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
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")
    return await get_events_in_range(db, current_user.family_id, start_dt, end_dt)


@router.post("/events", response_model=CalendarEventResponse, status_code=201)
async def create_event(
    data: CreateEventRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = await get_or_create_internal_source(db, current_user.family_id)
    try:
        start_dt = datetime.fromisoformat(data.start_dt)
        end_dt = datetime.fromisoformat(data.end_dt)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")
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
    event, color_hex = await _load_event_with_source(db, event_id, current_user.family_id)
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
    values = {}
    if data.title is not None:
        values["title"] = data.title
    if data.start_dt is not None:
        values["start_dt"] = datetime.fromisoformat(data.start_dt)
    if data.end_dt is not None:
        values["end_dt"] = datetime.fromisoformat(data.end_dt)
    if data.all_day is not None:
        values["all_day"] = data.all_day
    if data.location is not None:
        values["location"] = data.location
    if data.description is not None:
        values["description"] = data.description
    if values:
        await db.execute(
            sql_update(CalendarEvent)
            .where(CalendarEvent.id == event_id)
            .values(**values)
        )
        await db.flush()
    event, color_hex = await _load_event_with_source(db, event_id, current_user.family_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return _build_event_response(event, color_hex)


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event, _ = await _load_event_with_source(db, event_id, current_user.family_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.execute(
        sql_update(CalendarEvent)
        .where(CalendarEvent.id == event_id)
        .values(is_deleted=True)
    )
    await db.flush()
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
    source.enabled = False
    await db.flush()
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
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"ok": True, "message": "Sync triggered"}


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
        select(CalendarEvent, CalendarSource.color_hex)
        .join(CalendarSource, CalendarEvent.source_id == CalendarSource.id)
        .where(
            CalendarEvent.id == event_id,
            CalendarEvent.is_deleted == False,
            CalendarSource.family_id == family_id,
        )
    )
    row = result.one_or_none()
    if not row:
        return None, None
    return row[0], row[1]
