from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings

from app.jobs.backup import register_backup_job
from app.jobs.calendar_sync import register_sync_jobs

# Cron jobs (the daily backup at BACKUP_TIME) run in the configured TIMEZONE,
# not the container's UTC clock.
scheduler = AsyncIOScheduler(timezone=settings.timezone)


async def start_scheduler():
    register_sync_jobs(scheduler)
    register_backup_job(scheduler)
    scheduler.start()


async def stop_scheduler():
    scheduler.shutdown()
