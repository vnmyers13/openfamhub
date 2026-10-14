"""Weekly shopping-list reset for every family (each family's Monday).

Runs hourly and at startup on the existing scheduler. Bought items from
before this week are archived (kept as purchase history, never deleted);
unbought items generated from a past week's plan are dropped. Idempotent,
so reruns are free and downtime is caught up. (v0.29 had this job but never
registered it.)
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.family import Family
from app.services.meals import weekly_reset

logger = logging.getLogger(__name__)

session_factory = AsyncSessionLocal  # tests swap this for the test session


async def run_shopping_reset(now: Optional[datetime] = None) -> tuple[int, int]:
    now = now or datetime.now(timezone.utc)
    archived = dropped = 0
    async with session_factory() as db:
        families = list((await db.execute(select(Family).where(Family.is_deleted == False))).scalars().all())  # noqa: E712
        for family in families:
            a, d = await weekly_reset(db, family, now)
            archived, dropped = archived + a, dropped + d
        await db.commit()
    if archived or dropped:
        logger.info("Shopping reset: archived %s bought items, dropped %s stale plan items", archived, dropped)
    return archived, dropped


def register_shopping_reset_job(scheduler) -> None:
    scheduler.add_job(
        run_shopping_reset, "cron", minute=15, id="shopping_reset",
        replace_existing=True, next_run_time=datetime.now(scheduler.timezone),
    )
