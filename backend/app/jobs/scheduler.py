from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.jobs.backup import register_backup_job
from app.jobs.calendar_sync import register_sync_jobs

scheduler = AsyncIOScheduler()


async def start_scheduler():
    register_sync_jobs(scheduler)
    register_backup_job(scheduler)
    scheduler.start()


async def stop_scheduler():
    scheduler.shutdown()
