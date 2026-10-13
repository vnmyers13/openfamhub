"""Phase 6 rules shared by the rewards API, the chores API and the allowance job.

- Balances are sums of the points ledger; nothing stores a balance.
- A streak is a run of family-local days with at least one (not undone) chore
  completion, ending today or yesterday (today isn't over yet).
- Badges are earned once per person (unique row); a badge's bonus points are a
  ledger row keyed by that UserBadge, so they can't be credited twice.
- Allowance pays each Monday at 07:00 family time, at most once per week
  (unique user + week), and catches up missed weeks (capped) on the next run.
"""
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chores import ChoreCompletion, PointsEntry
from app.models.family import Family
from app.models.rewards import AllowanceEntry, AllowancePlan, BadgeDefinition, UserBadge
from app.models.user import User

PAYOUT_TIME = time(7)
CATCH_UP_WEEKS = 8
BADGE_KINDS = ("streak_days", "chores_completed", "points_earned")
CHORE_SOURCES = ("chore", "chore_undo")
EARNED_SOURCES = CHORE_SOURCES + ("badge",)  # what counts as "earned this week"


def zone_for(tz_name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


async def family_zone(db: AsyncSession, family_id: str) -> ZoneInfo:
    family = await db.get(Family, family_id)
    return zone_for(family.timezone if family else None)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def local_today(zone: ZoneInfo, now: Optional[datetime] = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(zone).date()


# ---- points -------------------------------------------------------------------

async def points_balance(db: AsyncSession, family_id: str, user_id: str) -> int:
    return (await db.execute(
        select(func.coalesce(func.sum(PointsEntry.delta), 0))
        .where(PointsEntry.family_id == family_id, PointsEntry.user_id == user_id)
    )).scalar()


async def _sums_by_user(db: AsyncSession, family_id: str, *where) -> dict[str, int]:
    rows = await db.execute(
        select(PointsEntry.user_id, func.sum(PointsEntry.delta))
        .where(PointsEntry.family_id == family_id, *where).group_by(PointsEntry.user_id)
    )
    return {uid: total or 0 for uid, total in rows.all()}


# ---- streaks --------------------------------------------------------------------

async def completion_days(db: AsyncSession, family_id: str, user_id: str, zone: ZoneInfo) -> set[date]:
    done = (await db.execute(
        select(ChoreCompletion.completed_at)
        .where(ChoreCompletion.family_id == family_id, ChoreCompletion.credited_to == user_id,
               ChoreCompletion.undone_at.is_(None))
    )).scalars().all()
    return {c.astimezone(zone).date() for c in done}


def streak_from(days: set[date], today: date) -> int:
    streak, day = 0, today if today in days else today - timedelta(days=1)
    while day in days:
        streak, day = streak + 1, day - timedelta(days=1)
    return streak


async def streak_days(db: AsyncSession, family_id: str, user_id: str, zone: ZoneInfo,
                      today: Optional[date] = None) -> int:
    days = await completion_days(db, family_id, user_id, zone)
    return streak_from(days, today or local_today(zone))


# ---- badges ---------------------------------------------------------------------

async def _metrics(db: AsyncSession, family_id: str, user_id: str, zone: ZoneInfo,
                   today: Optional[date] = None) -> dict[str, int]:
    completed = (await db.execute(
        select(func.count()).select_from(ChoreCompletion)
        .where(ChoreCompletion.family_id == family_id, ChoreCompletion.credited_to == user_id,
               ChoreCompletion.undone_at.is_(None))
    )).scalar()
    earned = (await db.execute(
        select(func.coalesce(func.sum(PointsEntry.delta), 0))
        .where(PointsEntry.family_id == family_id, PointsEntry.user_id == user_id,
               PointsEntry.source_type.in_(CHORE_SOURCES))
    )).scalar()
    return {
        "chores_completed": completed,
        "points_earned": earned,
        "streak_days": await streak_days(db, family_id, user_id, zone, today),
    }


async def award_badges(db: AsyncSession, family_id: str, user_id: str,
                       badges: Optional[Iterable[BadgeDefinition]] = None,
                       zone: Optional[ZoneInfo] = None, today: Optional[date] = None) -> list[UserBadge]:
    """Give `user_id` every active badge they now qualify for and don't have yet."""
    if badges is None:
        badges = (await db.execute(
            select(BadgeDefinition).where(BadgeDefinition.family_id == family_id, BadgeDefinition.is_active == True)  # noqa: E712
        )).scalars().all()
    badges = [b for b in badges if b.is_active]
    if not badges:
        return []
    have = set((await db.execute(select(UserBadge.badge_id).where(UserBadge.user_id == user_id))).scalars().all())
    todo = [b for b in badges if b.id not in have]
    if not todo:
        return []
    metrics = await _metrics(db, family_id, user_id, zone or await family_zone(db, family_id), today)
    now = datetime.now(timezone.utc)
    awarded = []
    for badge in todo:
        if metrics.get(badge.kind, 0) < badge.threshold:
            continue
        earned = UserBadge(family_id=family_id, user_id=user_id, badge_id=badge.id, earned_at=now)
        db.add(earned)
        await db.flush()
        if badge.bonus_points:
            db.add(PointsEntry(family_id=family_id, user_id=user_id, delta=badge.bonus_points,
                               reason=f"Badge: {badge.name}", source_type="badge", source_id=earned.id,
                               created_at=now))
        awarded.append(earned)
    if awarded:
        await db.flush()
    return awarded


async def earners(db: AsyncSession, family_id: str) -> list[User]:
    """Family members who take part in chores and rewards (everyone but viewers)."""
    rows = await db.execute(
        select(User).where(User.family_id == family_id, User.is_deleted == False, User.role != "viewer")  # noqa: E712
    )
    return sorted(rows.scalars().all(), key=lambda u: u.display_name.lower())


async def award_badge_to_all(db: AsyncSession, family_id: str, badge: BadgeDefinition) -> int:
    zone = await family_zone(db, family_id)
    count = 0
    for user in await earners(db, family_id):
        count += len(await award_badges(db, family_id, user.id, [badge], zone))
    return count


# ---- progress -------------------------------------------------------------------

@dataclass
class ProgressRow:
    user_id: str
    display_name: str
    color_hex: str
    avatar_value: Optional[str]
    points_balance: int
    points_this_week: int
    streak_days: int
    badges: list[dict] = field(default_factory=list)


async def progress(db: AsyncSession, family_id: str, today: Optional[date] = None) -> list[ProgressRow]:
    zone = await family_zone(db, family_id)
    today = today or local_today(zone)
    monday = datetime.combine(week_start(today), time(0), zone).astimezone(timezone.utc)
    balances = await _sums_by_user(db, family_id)
    this_week = await _sums_by_user(db, family_id, PointsEntry.source_type.in_(EARNED_SOURCES),
                                    PointsEntry.created_at >= monday)
    earned = (await db.execute(
        select(UserBadge.user_id, BadgeDefinition)
        .join(BadgeDefinition, BadgeDefinition.id == UserBadge.badge_id)
        .where(UserBadge.family_id == family_id).order_by(UserBadge.earned_at)
    )).all()
    badges: dict[str, list[dict]] = {}
    for uid, badge in earned:
        badges.setdefault(uid, []).append({"id": badge.id, "name": badge.name, "icon": badge.icon})
    rows = []
    for user in await earners(db, family_id):
        rows.append(ProgressRow(
            user_id=user.id, display_name=user.display_name, color_hex=user.color_hex,
            avatar_value=user.avatar_value, points_balance=balances.get(user.id, 0),
            points_this_week=max(this_week.get(user.id, 0), 0),
            streak_days=await streak_days(db, family_id, user.id, zone, today),
            badges=badges.get(user.id, []),
        ))
    return rows


# ---- allowance ------------------------------------------------------------------

def payout_week_due(now_local: datetime) -> date:
    """The Monday of the latest payout that has come due by `now_local`."""
    monday = week_start(now_local.date())
    if now_local < datetime.combine(monday, PAYOUT_TIME, now_local.tzinfo):
        monday -= timedelta(weeks=1)
    return monday


def first_payout_week(now_local: datetime) -> date:
    """A plan set now first pays at the next Monday 07:00."""
    return payout_week_due(now_local) + timedelta(weeks=1)


def next_payout(plan: Optional[AllowancePlan], now_local: datetime) -> Optional[date]:
    if plan is None or plan.weekly_cents <= 0:
        return None
    return max(plan.start_week, payout_week_due(now_local) + timedelta(weeks=1))


async def allowance_balance(db: AsyncSession, family_id: str, user_id: str) -> int:
    return (await db.execute(
        select(func.coalesce(func.sum(AllowanceEntry.delta_cents), 0))
        .where(AllowanceEntry.family_id == family_id, AllowanceEntry.user_id == user_id)
    )).scalar()


async def credit_allowances(db: AsyncSession, family: Family, now: datetime) -> int:
    """Pay every due, unpaid week for each plan in `family`. Idempotent."""
    zone = zone_for(family.timezone)
    due = payout_week_due(now.astimezone(zone))
    plans = (await db.execute(
        select(AllowancePlan)
        .join(User, User.id == AllowancePlan.user_id)
        .where(AllowancePlan.family_id == family.id, AllowancePlan.weekly_cents > 0, User.is_deleted == False)  # noqa: E712
    )).scalars().all()
    created = 0
    for plan in plans:
        first = max(plan.start_week, due - timedelta(weeks=CATCH_UP_WEEKS - 1))
        if first > due:
            continue
        paid = set((await db.execute(
            select(AllowanceEntry.week_start)
            .where(AllowanceEntry.user_id == plan.user_id, AllowanceEntry.week_start >= first,
                   AllowanceEntry.week_start <= due)
        )).scalars().all())
        week = first
        while week <= due:
            if week not in paid:
                db.add(AllowanceEntry(
                    family_id=family.id, user_id=plan.user_id, delta_cents=plan.weekly_cents,
                    reason=f"Weekly allowance (week of {week.isoformat()})", source_type="weekly",
                    source_id=f"{plan.user_id}:{week.isoformat()}", week_start=week,
                    created_at=datetime.now(timezone.utc),
                ))
                created += 1
            week += timedelta(weeks=1)
    if created:
        await db.flush()
    return created


def new_source_id() -> str:
    return str(uuid.uuid4())
