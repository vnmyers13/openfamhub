"""Pay weekly allowances (Mondays 07:00 family time) for every family.

Runs hourly and once at startup on the existing scheduler. Each run pays only
weeks that are due and not yet paid (unique user + week), so reruns are free
and a server that was down on Monday catches up on its next run.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.family import Family
from app.services.rewards import credit_allowances

logger = logging.getLogger(__name__)

session_factory = AsyncSessionLocal  # tests swap this for the test session


async def run_allowance(now: Optional[datetime] = None) -> int:
    now = now or datetime.now(timezone.utc)
    created = 0
    async with session_factory() as db:
        families = list((await db.execute(select(Family).where(Family.is_deleted == False))).scalars().all())  # noqa: E712
        for family in families:
            created += await credit_allowances(db, family, now)
        await db.commit()
    if created:
        logger.info("Paid %s weekly allowances", created)
    return created


def register_allowance_job(scheduler) -> None:
    scheduler.add_job(
        run_allowance, "cron", minute=10, id="allowance",
        replace_existing=True, next_run_time=datetime.now(scheduler.timezone),
    )
