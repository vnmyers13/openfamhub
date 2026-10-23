from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings

from app.jobs.backup import register_backup_job
from app.jobs.calendar_sync import register_sync_jobs
from app.jobs.calendar_subscriptions import register_calendar_subscription_jobs
from app.jobs.chore_generator import register_chore_job
from app.jobs.allowance import register_allowance_job
from app.jobs.shopping_reset import register_shopping_reset_job
from app.jobs.reminders import register_reminder_job
from app.jobs.home_assistant import register_home_assistant_job

# Cron jobs (the daily backup at BACKUP_TIME) run in the configured TIMEZONE,
# not the container's UTC clock.
scheduler = AsyncIOScheduler(timezone=settings.timezone)


async def start_scheduler(family_timezone: str | None = None):
    register_sync_jobs(scheduler)
    register_calendar_subscription_jobs(scheduler)
    register_backup_job(scheduler, family_timezone)
    register_chore_job(scheduler)
    register_allowance_job(scheduler)
    register_shopping_reset_job(scheduler)
    register_reminder_job(scheduler)
    register_home_assistant_job(scheduler)
    scheduler.start()


async def stop_scheduler():
    scheduler.shutdown()
