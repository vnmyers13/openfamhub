"""The family media library: checking, processing and storing uploads.

Uploads are streamed to a temp file with a running size check (the body is
never trusted to be small, and the client's Content-Type is never trusted at
all: the type comes from the file's first bytes). Only processed renditions
are kept; the uploaded original is deleted, so location metadata (EXIF GPS,
MP4 location tags) never stays on disk:

  photo -> wall.jpg (long edge <= 1920) + thumb.jpg (<= 400), EXIF dropped,
           camera rotation applied first.
  video -> wall.mp4 (H.264/AAC, <= 1920x1080, all metadata dropped, faststart)
           + thumb.jpg, converted in the background by ffmpeg.

Files live under MEDIA_ROOT/<family_id>/<media_id>/. ffmpeg comes from
imageio-ffmpeg's static build unless one is on PATH.
"""
import asyncio
import logging
import os
import re
import shutil
import uuid
from contextlib import suppress
from pathlib import Path
from typing import AsyncIterator, Callable

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.events import publish_queued, queue_event
from app.models.media import Media

logger = logging.getLogger(__name__)

_DATA_ROOT = Path(os.environ.get("DATA_PATH", Path(__file__).resolve().parents[3] / "data"))
MEDIA_ROOT = _DATA_ROOT / "photos" / "media"

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # anything bigger is refused before it's read
MAX_PHOTO_BYTES = 30 * 1024 * 1024
MAX_VIDEO_SECONDS = 10 * 60
MAX_PIXELS = 120_000_000  # decompression-bomb guard (a 12000x10000 image)
WALL_EDGE = 1920
THUMB_EDGE = 400
VARIANTS = {"wall", "thumb"}

# Background video jobs use their own session; tests swap this out.
session_factory: Callable = AsyncSessionLocal
_jobs: set[asyncio.Task] = set()
_ffmpeg_slot = asyncio.Semaphore(1)  # one conversion at a time on a small server


class MediaError(Exception):
    """A problem with an upload, with the HTTP status it should produce."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---- files ----------------------------------------------------------------

def item_dir(item: Media) -> Path:
    return MEDIA_ROOT / item.family_id / item.id


def variant_path(item: Media, variant: str) -> Path | None:
    if variant not in VARIANTS:
        return None
    name = "thumb.jpg" if variant == "thumb" else ("wall.mp4" if item.kind == "video" else "wall.jpg")
    path = item_dir(item) / name
    return path if path.is_file() else None


def media_type(item: Media, variant: str) -> str:
    return "video/mp4" if item.kind == "video" and variant == "wall" else "image/jpeg"


def remove_files(item: Media) -> None:
    shutil.rmtree(item_dir(item), ignore_errors=True)


async def save_upload(chunks: AsyncIterator[bytes], limit: int = None) -> Path:
    """Stream a request body to a temp file, stopping once it passes the limit."""
    limit = MAX_UPLOAD_BYTES if limit is None else limit
    tmp_dir = MEDIA_ROOT / ".incoming"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / f"{uuid.uuid4().hex}.upload"
    size = 0
    try:
        with path.open("wb") as f:
            async for chunk in chunks:
                size += len(chunk)
                if size > limit:
                    raise MediaError("That file is too large to upload", 413)
                f.write(chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    if size == 0:
        path.unlink(missing_ok=True)
        raise MediaError("The upload was empty")
    return path


# ---- type detection --------------------------------------------------------

_VIDEO_BRANDS = {b"isom", b"iso2", b"iso4", b"iso5", b"iso6", b"mp41", b"mp42", b"avc1",
                 b"M4V ", b"M4VP", b"qt  ", b"3gp4", b"3gp5", b"3g2a", b"dash", b"MSNV"}
_HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1", b"avif"}


def sniff(head: bytes) -> str:
    """'photo' or 'video' from a file's first bytes; anything else raises 415."""
    if head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG\r\n\x1a\n") \
            or head[:6] in (b"GIF87a", b"GIF89a") or (head[:4] == b"RIFF" and head[8:12] == b"WEBP"):
        return "photo"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in _HEIF_BRANDS:
            raise MediaError(
                "HEIC/HEIF photos aren't supported yet. On iPhone, set Settings › Camera › Formats "
                "to Most Compatible, or share the photo as JPEG.", 415)
        if brand in _VIDEO_BRANDS:
            return "video"
    if head.startswith(b"\x1a\x45\xdf\xa3"):  # Matroska/WebM
        return "video"
    raise MediaError("Only photos (JPEG, PNG, WebP, GIF) and videos (MP4, MOV, WebM) can be added", 415)


# ---- photos ----------------------------------------------------------------

def process_photo(src: Path, out_dir: Path) -> tuple[int, int, int]:
    """Write wall.jpg and thumb.jpg without metadata. Returns (width, height, bytes)."""
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(src) as img:
            img.seek(0)  # first frame of an animated GIF/WebP
            img = ImageOps.exif_transpose(img)  # apply the camera's rotation, then forget it
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                background = Image.new("RGB", img.size, (0, 0, 0))
                background.paste(img, mask=img.getchannel("A"))
                img = background
            else:
                img = img.convert("RGB")
            out_dir.mkdir(parents=True, exist_ok=True)
            wall = img.copy()
            wall.thumbnail((WALL_EDGE, WALL_EDGE), Image.Resampling.LANCZOS)
            # No exif= argument: the saved JPEGs carry no EXIF (so no GPS).
            wall.save(out_dir / "wall.jpg", "JPEG", quality=85, optimize=True, progressive=True)
            thumb = img.copy()
            thumb.thumbnail((THUMB_EDGE, THUMB_EDGE), Image.Resampling.LANCZOS)
            thumb.save(out_dir / "thumb.jpg", "JPEG", quality=80, optimize=True)
            return wall.width, wall.height, (out_dir / "wall.jpg").stat().st_size
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise MediaError("That photo couldn't be read; it may be damaged") from exc


# ---- videos ----------------------------------------------------------------

def ffmpeg_exe() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


async def _ffmpeg(*args: str, timeout: float = 30 * 60) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_exe(), "-hide_banner", "-nostdin", *args,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise MediaError("Converting the video took too long")
    return proc.returncode, err.decode(errors="replace")


_DURATION = re.compile(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)")
_SIZE = re.compile(r"Stream #\S+.*Video: .*?, (\d{2,5})x(\d{2,5})")


async def probe_video(path: Path) -> float:
    """Check a video is readable and not too long; returns its duration."""
    _, info = await _ffmpeg("-i", str(path))
    if "Video:" not in info:
        raise MediaError("That video couldn't be read; it may be damaged")
    match = _DURATION.search(info)
    if not match:
        raise MediaError("That video couldn't be read; it may be damaged")
    h, m, s = match.groups()
    duration = int(h) * 3600 + int(m) * 60 + float(s)
    if duration > MAX_VIDEO_SECONDS:
        raise MediaError(f"Videos can be up to {MAX_VIDEO_SECONDS // 60} minutes long; that one is too long")
    return duration


async def transcode_video(src: Path, out_dir: Path) -> tuple[int, int, int]:
    """Write wall.mp4 (no metadata) and thumb.jpg. Returns (width, height, bytes)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    wall = out_dir / "wall.mp4"
    code, err = await _ffmpeg(
        "-y", "-i", str(src),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-map_metadata", "-1", "-map_chapters", "-1",  # drop location, titles, dates
        "-vf", "scale='min(1920,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease,"
               "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-level", "4.1",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        "-movflags", "+faststart",
        str(wall),
    )
    if code != 0 or not wall.is_file():
        raise MediaError(f"ffmpeg exited with code {code}: {err.strip().splitlines()[-1] if err.strip() else ''}")
    _, info = await _ffmpeg("-i", str(wall))
    size = _SIZE.search(info)
    width, height = (int(size.group(1)), int(size.group(2))) if size else (None, None)
    for seek in ("1", "0"):  # a frame one second in, or the first for very short clips
        code, _ = await _ffmpeg("-y", "-ss", seek, "-i", str(wall), "-frames:v", "1",
                                "-vf", f"scale='min({THUMB_EDGE},iw)':-2", str(out_dir / "thumb.jpg"))
        if code == 0 and (out_dir / "thumb.jpg").is_file():
            break
    return width, height, wall.stat().st_size


async def _run_video_job(media_id: str, src: Path) -> None:
    async with _ffmpeg_slot:
        async with session_factory() as db:
            item = await db.get(Media, media_id)
            if item is None:
                src.unlink(missing_ok=True)
                return
            try:
                width, height, size = await transcode_video(src, item_dir(item))
                item.width, item.height, item.size_bytes = width, height, size
                item.status, item.error = "ready", None
            except Exception as exc:  # recorded on the item, shown in the library
                logger.warning("Video %s failed: %s", media_id, exc)
                remove_files(item)
                item.status, item.error = "failed", str(exc) or exc.__class__.__name__
            finally:
                src.unlink(missing_ok=True)
            queue_event(db, "media_updated", {"media_id": media_id})
            await db.commit()
            await publish_queued(db)


def start_video_job(media_id: str, src: Path) -> None:
    task = asyncio.create_task(_run_video_job(media_id, src))
    _jobs.add(task)
    task.add_done_callback(_jobs.discard)


async def wait_for_jobs() -> None:
    """Wait for background conversions (used by tests and shutdown)."""
    while _jobs:
        await asyncio.gather(*list(_jobs), return_exceptions=True)


async def fail_interrupted(db: AsyncSession) -> int:
    """At startup: conversions that were running when the API stopped will never finish."""
    result = await db.execute(
        update(Media).where(Media.status == "processing")
        .values(status="failed", error="Interrupted by a restart; please upload it again")
        .execution_options(synchronize_session="fetch")
    )
    return result.rowcount or 0


# ---- queries ---------------------------------------------------------------

async def family_media(db: AsyncSession, family_id: str, *, ready_only: bool = False) -> list[Media]:
    query = select(Media).where(Media.family_id == family_id)
    if ready_only:
        query = query.where(Media.status == "ready")
    result = await db.execute(query.order_by(Media.created_at.desc(), Media.id.desc()))
    return list(result.scalars().all())


async def get_family_item(db: AsyncSession, family_id: str, media_id: str) -> Media | None:
    item = await db.get(Media, media_id)
    return item if item is not None and item.family_id == family_id else None


async def cleanup_incoming() -> None:
    with suppress(FileNotFoundError):
        for f in (MEDIA_ROOT / ".incoming").iterdir():
            f.unlink(missing_ok=True)
