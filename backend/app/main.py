from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.config import get_settings
from app.routers import auth, users, events, calendar, announcements, wall, chores, rewards, meals, books, weather
from app.jobs.chore_generator import generate_chore_instances
from app.jobs.allowance_distributor import distribute_weekly_allowance

scheduler = None

app = FastAPI(
    title="OpenFamHub",
    version=get_settings().app_version,
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
app.include_router(chores.router, prefix="/api/chores", tags=["chores"])
app.include_router(rewards.router, prefix="/api/rewards", tags=["rewards"])
app.include_router(meals.router, prefix="/api/meals", tags=["meals"])
app.include_router(books.router, prefix="/api/books", tags=["books"])
app.include_router(weather.router, prefix="/api/weather", tags=["weather"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": get_settings().app_version}


from app.core.database import engine
from app.models.base import Base
from app.models import (
    User,
    Event,
    CalendarSource,
    CalendarEvent,
    SyncLog,
    Announcement,
    Chore,
    ChoreInstance,
    ChoreCompletionLog,
    RewardPointsLedger,
    AllowanceLedger,
    Reward,
    RewardRequest,
    BadgeDefinition,
    UserBadge,
    UserStreak,
    Book,
)


@app.on_event("startup")
async def on_startup():
    global scheduler
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.core.database import async_session_factory
    scheduler = AsyncIOScheduler()

    async def chore_job():
        async with async_session_factory() as session:
            await generate_chore_instances(session)
            await session.commit()

    async def allowance_job():
        async with async_session_factory() as session:
            await distribute_weekly_allowance(session)
            await session.commit()

    scheduler.add_job(chore_job, "cron", hour=6, minute=0, id="chore_generator", replace_existing=True)
    scheduler.add_job(allowance_job, "cron", day_of_week="mon", hour=7, minute=0, id="allowance_distributor", replace_existing=True)
    scheduler.start()


@app.on_event("shutdown")
async def on_shutdown():
    global scheduler
    await engine.dispose()
    if scheduler:
        scheduler.shutdown(wait=False)
