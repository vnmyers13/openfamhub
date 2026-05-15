import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import Base, engine

_DATA_ROOT = Path(os.environ.get("DATA_PATH", Path(__file__).resolve().parent.parent.parent.parent / "data"))
_PHOTOS_DIR = _DATA_ROOT / "photos"
_DB_DIR = _DATA_ROOT / "db"
_BACKUPS_DIR = _DATA_ROOT / "backups"


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(_PHOTOS_DIR / "originals", exist_ok=True)
    os.makedirs(_PHOTOS_DIR / "avatars", exist_ok=True)
    os.makedirs(_PHOTOS_DIR / "thumbnails", exist_ok=True)
    os.makedirs(_DB_DIR, exist_ok=True)
    os.makedirs(_BACKUPS_DIR, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.jobs.scheduler import start_scheduler, stop_scheduler

    await start_scheduler()

    yield

    await stop_scheduler()


app = FastAPI(
    title="HomeHub",
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


os.makedirs(_PHOTOS_DIR, exist_ok=True)
app.mount("/photos", StaticFiles(directory=str(_PHOTOS_DIR)), name="photos")

from app.routers import auth, users, calendar, integrations, ws

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])
app.include_router(ws.router, prefix="/api/ws", tags=["ws"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.app_version}
