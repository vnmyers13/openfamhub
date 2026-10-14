"""One call for the dashboard (Phase 8): today's events, my chores and the
family's, my points and allowance, today's and this week's meals, upcoming
birthdays and recent announcements. (v0.29's dashboard called four
/api/dashboard/* routes that didn't exist.) Weather is separate (/api/weather)
so a slow forecast can't hold the rest up."""
from datetime import datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.chores import ChoreInstance, ChoreTemplate
from app.models.meals import MealPlanEntry
from app.models.user import User
from app.routers.announcements import recent, to_announcement
from app.schemas.family_info import ChoreCounts, DashboardSummary, MealToday, UpcomingBirthday
from app.schemas.meals import SLOTS
from app.services import birthdays, rewards
from app.services.calendar import get_events_in_range, only_mine

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def summary(scope: Literal["family", "mine"] = "family", db: AsyncSession = Depends(get_db),
                  user: User = Depends(get_current_user)):
    zone = await rewards.family_zone(db, user.family_id)
    today = rewards.local_today(zone)
    day_start = datetime.combine(today, time(0), zone).astimezone(timezone.utc)
    events = await get_events_in_range(db, user.family_id, day_start, day_start + timedelta(days=1))
    if scope == "mine":
        events = only_mine(events, user.id)

    rows = (await db.execute(
        select(ChoreInstance.status, func.coalesce(ChoreInstance.assigned_to, ChoreInstance.claimed_by), func.count())
        .join(ChoreTemplate, ChoreTemplate.id == ChoreInstance.template_id)
        .where(ChoreInstance.family_id == user.family_id, ChoreInstance.due_date == today,
               ChoreTemplate.routine_id.is_(None))
        .group_by(ChoreInstance.status, func.coalesce(ChoreInstance.assigned_to, ChoreInstance.claimed_by))
    )).all()
    counts = {"mine_open": 0, "mine_done": 0, "family_open": 0, "family_done": 0}
    for status, owner, n in rows:
        done = status == "completed"
        if status == "missed":
            continue
        counts["family_done" if done else "family_open"] += n
        if owner == user.id:
            counts["mine_done" if done else "mine_open"] += n

    monday = rewards.week_start(today)
    meals = (await db.execute(
        select(MealPlanEntry).where(MealPlanEntry.family_id == user.family_id, MealPlanEntry.day >= monday,
                                    MealPlanEntry.day < monday + timedelta(days=7))
    )).scalars().all()
    meals = sorted(meals, key=lambda m: (m.day, SLOTS.index(m.slot) if m.slot in SLOTS else 9))
    as_meal = lambda m: MealToday(day=m.day, slot=m.slot, title=m.title, recipe_id=m.recipe_id)  # noqa: E731

    return DashboardSummary(
        today=today,
        events_today=[e.model_dump() for e in events],
        chores=ChoreCounts(**counts),
        points_balance=await rewards.points_balance(db, user.family_id, user.id),
        allowance_cents=await rewards.allowance_balance(db, user.family_id, user.id),
        meals_today=[as_meal(m) for m in meals if m.day == today],
        meals_week=[as_meal(m) for m in meals],
        birthdays=[UpcomingBirthday(**vars(b)) for b in await birthdays.upcoming(db, user.family_id, today, 30)],
        announcements=[to_announcement(a) for a in await recent(db, user.family_id, 5)],
    )


@router.get("/birthdays", response_model=list[UpcomingBirthday])
async def upcoming_birthdays(days: int = 60, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    zone = await rewards.family_zone(db, user.family_id)
    today = rewards.local_today(zone)
    return [UpcomingBirthday(**vars(b)) for b in await birthdays.upcoming(db, user.family_id, today, max(1, min(days, 366)))]
