from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_admin
from app.schemas.models import (
    CalendarSourceCreate, CalendarSourceUpdate, CalendarSourceResponse,
    CalendarEventResponse, SyncLogResponse,
)
from app.models.event import CalendarSource, CalendarEvent, SyncLog

router = APIRouter()


@router.get("/sources", response_model=list[CalendarSourceResponse])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(CalendarSource).order_by(CalendarSource.name))
    sources = result.scalars().all()

    return [
        CalendarSourceResponse(
            id=s.id,
            name=s.name,
            url=s.url,
            color_hex=s.color_hex,
            sync_interval_hours=s.sync_interval_hours,
            last_synced_at=s.last_synced_at,
            is_active=s.is_active,
            created_at=str(s.created_at),
            updated_at=str(s.updated_at),
        )
        for s in sources
    ]


@router.post("/sources", response_model=CalendarSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    req: CalendarSourceCreate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    source = CalendarSource(
        name=req.name,
        url=req.url,
        color_hex=req.color_hex,
        sync_interval_hours=req.sync_interval_hours,
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)

    return CalendarSourceResponse(
        id=source.id,
        name=source.name,
        url=source.url,
        color_hex=source.color_hex,
        sync_interval_hours=source.sync_interval_hours,
        last_synced_at=source.last_synced_at,
        is_active=source.is_active,
        created_at=str(source.created_at),
        updated_at=str(source.updated_at),
    )


@router.patch("/sources/{source_id}", response_model=CalendarSourceResponse)
async def update_source(
    source_id: str,
    req: CalendarSourceUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(CalendarSource).where(CalendarSource.id == source_id))
    source = result.scalar_one_or_none()

    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(source, key, value)

    await db.flush()
    await db.refresh(source)

    return CalendarSourceResponse(
        id=source.id,
        name=source.name,
        url=source.url,
        color_hex=source.color_hex,
        sync_interval_hours=source.sync_interval_hours,
        last_synced_at=source.last_synced_at,
        is_active=source.is_active,
        created_at=str(source.created_at),
        updated_at=str(source.updated_at),
    )


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(CalendarSource).where(CalendarSource.id == source_id))
    source = result.scalar_one_or_none()

    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    await db.delete(source)
    await db.flush()

    return {"message": "Source deleted"}


@router.post("/sources/{source_id}/sync")
async def trigger_sync(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(CalendarSource).where(CalendarSource.id == source_id))
    source = result.scalar_one_or_none()

    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    from app.services.calendar_service import sync_calendar_source
    sync_log = await sync_calendar_source(db, source)
    await db.commit()

    return {
        "message": "Sync completed",
        "source_id": source_id,
        "events_imported": sync_log.events_imported,
        "events_deleted": sync_log.events_deleted,
        "status": sync_log.status,
        "errors": sync_log.errors,
    }


@router.get("/sync-log", response_model=list[SyncLogResponse])
async def get_sync_log(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(
        select(SyncLog).order_by(SyncLog.started_at.desc()).limit(50)
    )
    logs = result.scalars().all()

    return [
        SyncLogResponse(
            id=log.id,
            source_id=log.source_id,
            events_imported=log.events_imported,
            events_deleted=log.events_deleted,
            errors=log.errors if isinstance(log.errors, list) else [],
            started_at=log.started_at,
            completed_at=log.completed_at,
            status=log.status,
        )
        for log in logs
    ]


@router.get("/events", response_model=list[CalendarEventResponse])
async def list_calendar_events(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CalendarEvent)
        .where(CalendarEvent.is_deleted == False)  # noqa: E712
        .order_by(CalendarEvent.start_time)
    )
    events = result.scalars().all()

    return [
        CalendarEventResponse(
            id=e.id,
            source_id=e.source_id,
            external_uid=e.external_uid,
            title=e.title,
            description=e.description,
            location=e.location,
            start_time=e.start_time,
            end_time=e.end_time,
            all_day=e.all_day,
            color_hex=e.color_hex,
            synced_at=e.synced_at,
        )
        for e in events
    ]
