import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import Base, engine

# Docker sets DATA_PATH=/data; outside Docker default to <repo>/data.
_DATA_ROOT = Path(os.environ.get("DATA_PATH", Path(__file__).resolve().parents[2] / "data"))
_PHOTOS_DIR = _DATA_ROOT / "photos"
_DB_DIR = _DATA_ROOT / "db"
_BACKUPS_DIR = _DATA_ROOT / "backups"


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(_PHOTOS_DIR / "media", exist_ok=True)
    os.makedirs(_DB_DIR, exist_ok=True)
    os.makedirs(_BACKUPS_DIR, exist_ok=True)

    # Alembic owns the schema. It runs in a worker thread because env.py starts
    # its own event loop. create_all afterwards is a no-op safety net.
    from app.core.migrate import upgrade_database

    await asyncio.to_thread(upgrade_database)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Video conversions that were running when the API stopped won't finish.
    from app.core.database import AsyncSessionLocal
    from app.services import media as media_service

    await media_service.cleanup_incoming()
    async with AsyncSessionLocal() as db:
        await media_service.fail_interrupted(db)
        await db.commit()

    from app.jobs.scheduler import start_scheduler, stop_scheduler

    await start_scheduler()

    yield

    await stop_scheduler()


app = FastAPI(
    title="OpenFamHub",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Family photos and videos are served only by /api/media and /api/wall/media,
# which check who is asking. (Before 0.84 all of data/photos was public here.)
from app.routers import auth, users, calendar, chores, family, integrations, media, wall

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])
app.include_router(wall.router, prefix="/api/wall", tags=["wall"])
app.include_router(media.router, prefix="/api/media", tags=["media"])
app.include_router(family.router, prefix="/api/family", tags=["family"])
app.include_router(chores.router, prefix="/api/chores", tags=["chores"])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": settings.app_version,
        # e.g. "0.30.17": which CI build is running ("dev" for local builds).
        "build": settings.openfamhub_build or settings.app_version,
        "commit": settings.openfamhub_commit or None,
    }
