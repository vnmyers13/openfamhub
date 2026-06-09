from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.models import EventCreate, EventUpdate, EventResponse
from app.models.event import Event

router = APIRouter()


@router.get("", response_model=list[EventResponse])
async def list_events(
    start: Optional[str] = Query(None, description="Start filter (ISO format)"),
    end: Optional[str] = Query(None, description="End filter (ISO format)"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    query = select(Event).where(Event.is_deleted == False)  # noqa: E712

    if start:
        query = query.where(Event.start_time >= start)
    if end:
        query = query.where(Event.end_time <= end)

    query = query.order_by(Event.start_time)
    result = await db.execute(query)
    events = result.scalars().all()

    return [
        EventResponse(
            id=e.id,
            title=e.title,
            description=e.description,
            location=e.location,
            start_time=e.start_time,
            end_time=e.end_time,
            is_all_day=e.is_all_day,
            created_by_id=e.created_by_id,
            assigned_to_id=e.assigned_to_id,
            color_hex=e.color_hex,
            created_at=str(e.created_at),
            updated_at=str(e.updated_at),
        )
        for e in events
    ]


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    req: EventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    event = Event(
        title=req.title,
        description=req.description,
        location=req.location,
        start_time=req.start_time,
        end_time=req.end_time,
        is_all_day=req.is_all_day,
        created_by_id=current_user["sub"],
        assigned_to_id=req.assigned_to_id,
        color_hex=req.color_hex,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)

    return EventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        location=event.location,
        start_time=event.start_time,
        end_time=event.end_time,
        is_all_day=event.is_all_day,
        created_by_id=event.created_by_id,
        assigned_to_id=event.assigned_to_id,
        color_hex=event.color_hex,
        created_at=str(event.created_at),
        updated_at=str(event.updated_at),
    )


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    req: EventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Event).where(Event.id == event_id, Event.is_deleted == False))  # noqa: E712
    event = result.scalar_one_or_none()

    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    if event.created_by_id != current_user["sub"] and current_user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(event, key, value)

    await db.flush()
    await db.refresh(event)

    return EventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        location=event.location,
        start_time=event.start_time,
        end_time=event.end_time,
        is_all_day=event.is_all_day,
        created_by_id=event.created_by_id,
        assigned_to_id=event.assigned_to_id,
        color_hex=event.color_hex,
        created_at=str(event.created_at),
        updated_at=str(event.updated_at),
    )


@router.delete("/{event_id}")
async def delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    if event.created_by_id != current_user["sub"] and current_user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    event.is_deleted = True
    await db.flush()

    return {"message": "Event deleted"}
