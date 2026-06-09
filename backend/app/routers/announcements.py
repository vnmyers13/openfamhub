from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.schemas.models import AnnouncementCreate, AnnouncementResponse
from app.models.event import Announcement

router = APIRouter()


@router.get("", response_model=list[AnnouncementResponse])
async def list_announcements(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Announcement)
        .where(Announcement.is_deleted == False)  # noqa: E712
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
    )
    announcements = result.scalars().all()

    return [
        AnnouncementResponse(
            id=a.id,
            author_id=a.author_id,
            content=a.content,
            is_pinned=a.is_pinned,
            created_at=str(a.created_at),
            updated_at=str(a.updated_at),
        )
        for a in announcements
    ]


@router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    req: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    announcement = Announcement(
        author_id=current_user["sub"],
        content=req.content,
    )
    db.add(announcement)
    await db.flush()
    await db.refresh(announcement)

    return AnnouncementResponse(
        id=announcement.id,
        author_id=announcement.author_id,
        content=announcement.content,
        is_pinned=announcement.is_pinned,
        created_at=str(announcement.created_at),
        updated_at=str(announcement.updated_at),
    )


@router.patch("/{announcement_id}/pin")
async def toggle_pin(
    announcement_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(
        select(Announcement).where(Announcement.id == announcement_id)
    )
    announcement = result.scalar_one_or_none()

    if announcement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")

    announcement.is_pinned = not announcement.is_pinned
    await db.flush()

    return {"message": f"Announcement {'pinned' if announcement.is_pinned else 'unpinned'}"}
