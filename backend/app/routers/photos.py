from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response
import os
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.event import Photo

router = APIRouter()


@router.get("")
async def list_photos(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Photo)
        .where(Photo.is_deleted == False)
        .order_by(Photo.created_at.desc())
    )
    photos = result.scalars().all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "file_path": p.file_path,
            "created_at": str(p.created_at),
        }
        for p in photos
    ]


@router.post("")
async def upload_photo(
    file: UploadFile = File(...),
    title: str = "",
    description: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type")

    photo_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    filename = f"{photo_id}{ext}"
    photos_dir = "/data/photos/wall"
    os.makedirs(photos_dir, exist_ok=True)
    file_path = os.path.join(photos_dir, filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    photo = Photo(
        title=title,
        description=description,
        file_path=file_path,
        created_by_id=current_user["sub"],
    )
    db.add(photo)
    await db.flush()
    await db.refresh(photo)

    return {
        "id": photo.id,
        "title": photo.title,
        "description": photo.description,
        "file_path": photo.file_path,
        "created_at": str(photo.created_at),
    }


@router.get("/{photo_id}")
async def get_photo(photo_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id)
    )
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return {
        "id": photo.id,
        "title": photo.title,
        "description": photo.description,
        "file_path": photo.file_path,
        "created_at": str(photo.created_at),
    }


@router.get("/serve/{filename}")
async def serve_photo(filename: str):
    file_path = os.path.join("/data/photos/wall", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(file_path)


@router.delete("/{photo_id}")
async def delete_photo(
    photo_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id)
    )
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    photo.is_deleted = True
    await db.flush()
    return {"message": "Photo deleted"}
