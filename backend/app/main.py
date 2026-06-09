import { FastAPI } from "fastapi"
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, users, events, calendar, announcements, wall

app = FastAPI(
    title="OpenFamHub",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
app.include_router(announcements.router, prefix="/api/announcements", tags=["announcements"])
app.include_router(wall.router, prefix="/wall", tags=["wall"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


from app.core.database import engine, Base
from app.models import user, event


@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.on_event("shutdown")
async def on_shutdown():
    await engine.dispose()
