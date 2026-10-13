"""Create upcoming chore instances and mark missed ones, for every family.

Runs hourly (and once at startup) on the existing scheduler: generation is
idempotent, so frequent runs are free, and each family's day rolls over within
the hour in its own timezone rather than at a fixed server time.
"""
import logging
from datetime import datetime

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.family import Family
from app.services.chores import family_today, generate_instances

logger = logging.getLogger(__name__)

session_factory = AsyncSessionLocal  # tests swap this for the test session


async def run_chore_generator() -> int:
    created = 0
    async with session_factory() as db:
        families = list((await db.execute(select(Family).where(Family.is_deleted == False))).scalars().all())  # noqa: E712
        for family in families:
            created += await generate_instances(db, family.id, family_today(family.timezone))
        await db.commit()
    if created:
        logger.info("Created %s chore instances", created)
    return created


def register_chore_job(scheduler) -> None:
    scheduler.add_job(
        run_chore_generator, "cron", minute=5, id="chore_generator",
        replace_existing=True, next_run_time=datetime.now(scheduler.timezone),
    )
