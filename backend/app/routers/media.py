"""Family media library: upload, list, view and delete photos and videos.

Files are only ever served through these routes (or the wall's), which check
the signed-in user's family; there is no public static route to them.
"""
import asyncio
from datetime import datetime, timezone
from typing import List
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import queue_event
from app.core.security import get_current_user, require_role
from app.models.media import Media
from app.models.user import User
from app.schemas.media import MediaResponse
from app.services import media as media_service
from app.services.media import MediaError

router = APIRouter()


def to_response(item: Media, prefix: str = "/api/media") -> MediaResponse:
    return MediaResponse(
        id=item.id, kind=item.kind, status=item.status, error=item.error,
        original_name=item.original_name, width=item.width, height=item.height,
        duration_s=item.duration_s, uploaded_by=item.uploaded_by, created_at=item.created_at,
        wall_url=f"{prefix}/{item.id}/wall", thumb_url=f"{prefix}/{item.id}/thumb",
    )


def serve_file(item: Media | None, variant: str) -> FileResponse:
    path = media_service.variant_path(item, variant) if item is not None and item.status == "ready" else None
    if path is None:
        raise HTTPException(status_code=404, detail="Not found")
    # Content never changes for a given id and variant, and it's private.
    return FileResponse(path, media_type=media_service.media_type(item, variant),
                        headers={"Cache-Control": "private, max-age=604800"})


@router.post("", status_code=201, response_model=MediaResponse,
             responses={202: {"model": MediaResponse, "description": "Video accepted; converting"}})
async def upload(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "member")),
):
    """Upload one photo or video as the raw request body (X-Filename names it).

    A raw body, not multipart, so the size limit applies while streaming
    instead of after the whole file has been buffered."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > media_service.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="That file is too large to upload")
    name = unquote(request.headers.get("x-filename", ""))[:256] or "upload"

    src = None
    try:
        src = await media_service.save_upload(request.stream())
        with src.open("rb") as f:
            kind = media_service.sniff(f.read(32))
        size = src.stat().st_size
        if kind == "photo" and size > media_service.MAX_PHOTO_BYTES:
            raise MediaError(f"Photos can be up to {media_service.MAX_PHOTO_BYTES // (1024 * 1024)} MB", 413)
        duration = await media_service.probe_video(src) if kind == "video" else None

        item = Media(family_id=current_user.family_id, uploaded_by=current_user.id, kind=kind,
                     status="processing", original_name=name, duration_s=duration,
                     created_at=datetime.now(timezone.utc))
        db.add(item)
        await db.flush()

        if kind == "photo":
            try:
                width, height, stored = await asyncio.to_thread(
                    media_service.process_photo, src, media_service.item_dir(item))
            except MediaError:
                await db.delete(item)
                await db.flush()
                raise
            item.width, item.height, item.size_bytes, item.status = width, height, stored, "ready"
            await db.flush()
            await db.refresh(item)
            queue_event(db, "media_updated", {"media_id": item.id})
            return to_response(item)

        # Videos convert in the background; the library shows "processing".
        await db.commit()
        await db.refresh(item)
        media_service.start_video_job(item.id, src)
        src = None  # the job owns (and deletes) the upload now
        return JSONResponse(status_code=202, content=to_response(item).model_dump(mode="json"))
    except MediaError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))
    finally:
        if src is not None:
            src.unlink(missing_ok=True)


@router.get("", response_model=List[MediaResponse])
async def list_media(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return [to_response(i) for i in await media_service.family_media(db, current_user.family_id)]


@router.get("/{media_id}/{variant}")
async def media_file(
    media_id: str, variant: str,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    return serve_file(await media_service.get_family_item(db, current_user.family_id, media_id), variant)


@router.delete("/{media_id}")
async def delete_media(media_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = await media_service.get_family_item(db, current_user.family_id, media_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    if current_user.role != "admin" and item.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can only remove photos and videos you added")
    media_service.remove_files(item)
    await db.delete(item)
    await db.flush()
    queue_event(db, "media_updated", {"media_id": media_id})
    return {"ok": True}
