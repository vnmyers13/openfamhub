"""Announcements (Phase 8): short family notes; pinned ones stay on top.
Signed-in members only (v0.29's list had no auth). Anyone but viewers can
post; the author or an admin can edit, pin or remove one."""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import queue_event
from app.core.security import get_current_user
from app.models.family_info import Announcement
from app.models.user import User
from app.schemas.family_info import AnnouncementCreate, AnnouncementResponse, AnnouncementUpdate

router = APIRouter()


def to_announcement(a: Announcement) -> AnnouncementResponse:
    return AnnouncementResponse(id=a.id, body=a.body, pinned=a.pinned, author_id=a.author_id, created_at=a.created_at)


async def recent(db: AsyncSession, family_id: str, limit: int) -> list[Announcement]:
    rows = (await db.execute(
        select(Announcement).where(Announcement.family_id == family_id)
        .order_by(Announcement.pinned.desc(), Announcement.created_at.desc()).limit(limit)
    )).scalars().all()
    return list(rows)


async def load(db: AsyncSession, user: User, announcement_id: str) -> Announcement:
    a = await db.get(Announcement, announcement_id)
    if a is None or a.family_id != user.family_id:
        raise HTTPException(status_code=404, detail="Announcement not found")
    if user.role != "admin" and a.author_id != user.id:
        raise HTTPException(status_code=403, detail="Only whoever posted it (or an admin) can change it")
    return a


@router.get("", response_model=List[AnnouncementResponse])
async def list_announcements(limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db),
                             user: User = Depends(get_current_user)):
    return [to_announcement(a) for a in await recent(db, user.family_id, limit)]


@router.post("", response_model=AnnouncementResponse, status_code=201)
async def post_announcement(data: AnnouncementCreate, db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_current_user)):
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers can't post announcements")
    a = Announcement(family_id=user.family_id, body=data.body, pinned=data.pinned, author_id=user.id,
                     created_at=datetime.now(timezone.utc))
    db.add(a)
    await db.flush()
    queue_event(db, "announcements_updated", {})
    return to_announcement(a)


@router.patch("/{announcement_id}", response_model=AnnouncementResponse)
async def edit_announcement(announcement_id: str, data: AnnouncementUpdate, db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_current_user)):
    a = await load(db, user, announcement_id)
    if data.body is not None:
        a.body = data.body
    if data.pinned is not None:
        a.pinned = data.pinned
    await db.flush()
    queue_event(db, "announcements_updated", {})
    return to_announcement(a)


@router.delete("/{announcement_id}")
async def delete_announcement(announcement_id: str, db: AsyncSession = Depends(get_db),
                              user: User = Depends(get_current_user)):
    a = await load(db, user, announcement_id)
    await db.delete(a)
    await db.flush()
    queue_event(db, "announcements_updated", {})
    return {"message": "Removed"}
