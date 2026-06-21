"""Dashboard aggregation router — serves summary data for the home dashboard."""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.models import (
    ChoreStatsResponse,
    RewardPointsLedgerEntry,
    AllowanceLedgerEntry,
    MealPlanResponse,
    MealPlanWeekResponse,
)
from app.models import (
    ChoreCompletionLog,
    RewardPointsLedger,
    AllowanceLedger,
    User,
    UserStreak,
    ChoreInstance,
    Chore,
)
from app.models.event import MealPlan

router = APIRouter()


# ─── Chores ──────────────────────────────────────────────────────────────────


@router.get("/chores/stats", response_model=ChoreStatsResponse)
async def get_chore_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["sub"]

    # Total completed chores
    result = await db.execute(
        select(func.count(ChoreCompletionLog.id)).where(ChoreCompletionLog.completed_by_id == user_id)
    )
    total_completed = result.scalar() or 0

    # Points earned from completions
    result = await db.execute(
        select(func.sum(ChoreCompletionLog.points_earned)).where(
            and_(ChoreCompletionLog.completed_by_id == user_id, ChoreCompletionLog.points_earned.isnot(None))
        )
    )
    points_earned = int(result.scalar() or 0)

    # Current streak & longest streak from UserStreak
    result = await db.execute(
        select(UserStreak.current_streak, UserStreak.longest_streak).where(UserStreak.user_id == user_id)
    )
    row = result.first()
    current_streak = row[0] if row else 0
    longest_streak = row[1] if row else 0

    return ChoreStatsResponse(
        total_completed=total_completed,
        current_streak=current_streak,
        longest_streak=longest_streak,
        points_earned=points_earned,
    )


@router.get("/chores/assigned")
async def get_assigned_chores(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["sub"]

    query = (
        select(ChoreInstance, Chore.title, Chore.point_value, User.name.label("assignee_name"))
        .join(Chore, ChoreInstance.chore_id == Chore.id)
        .join(User, ChoreInstance.assigned_to_id == User.id, isouter=True)
        .where(ChoreInstance.assigned_to_id == user_id)
        .where(ChoreInstance.status == "assigned")
        .order_by(ChoreInstance.due_date)
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "instance_id": r[0].id,
            "chore_title": r[1],
            "point_value": r[2],
            "due_date": str(r[0].due_date) if r[0].due_date else None,
            "status": r[0].status,
            "assignee_name": r[3],
        }
        for r in rows
    ]


@router.get("/chores/available")
async def get_available_chores(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["sub"]

    query = (
        select(ChoreInstance, Chore.title, Chore.point_value, User.name.label("assignee_name"))
        .join(Chore, ChoreInstance.chore_id == Chore.id)
        .join(User, ChoreInstance.assigned_to_id == User.id, isouter=True)
        .where(ChoreInstance.status == "pending")
        .where(
            or_(
                ChoreInstance.assigned_to_id == user_id,
                ChoreInstance.claimed_by_id == user_id,
                ChoreInstance.assigned_to_id.is_(None),
            )
        )
        .order_by(ChoreInstance.due_date)
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "instance_id": r[0].id,
            "chore_title": r[1],
            "point_value": r[2],
            "due_date": str(r[0].due_date) if r[0].due_date else None,
            "status": r[0].status,
            "assignee_name": r[3],
        }
        for r in rows
    ]


# ─── Rewards ─────────────────────────────────────────────────────────────────


@router.get("/rewards/points/balance")
async def get_dashboard_points_balance(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["sub"]

    result = await db.execute(
        select(func.sum(RewardPointsLedger.points)).where(RewardPointsLedger.user_id == user_id)
    )
    total = result.scalar() or 0

    result = await db.execute(
        select(RewardPointsLedger)
        .where(RewardPointsLedger.user_id == user_id)
        .order_by(RewardPointsLedger.created_at.desc())
        .limit(20)
    )
    entries = result.scalars().all()

    return {
        "balance": int(total),
        "transactions": [
            {
                "id": e.id,
                "user_id": e.user_id,
                "points": e.points,
                "type": e.type,
                "reference_id": e.reference_id,
                "description": e.description,
                "created_at": str(e.created_at),
            }
            for e in entries
        ],
    }


@router.get("/rewards/allowance/balance")
async def get_dashboard_allowance_balance(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["sub"]

    result = await db.execute(
        select(func.sum(AllowanceLedger.amount)).where(AllowanceLedger.user_id == user_id)
    )
    total = float(result.scalar() or 0)

    result = await db.execute(
        select(AllowanceLedger)
        .where(AllowanceLedger.user_id == user_id)
        .order_by(AllowanceLedger.created_at.desc())
        .limit(20)
    )
    entries = result.scalars().all()

    return {
        "balance": total,
        "transactions": [
            {
                "id": e.id,
                "user_id": e.user_id,
                "amount": e.amount,
                "type": e.type,
                "reference_id": e.reference_id,
                "description": e.description,
                "created_at": str(e.created_at),
            }
            for e in entries
        ],
    }


# ─── Meals ───────────────────────────────────────────────────────────────────


@router.get("/meals/plans", response_model=MealPlanWeekResponse)
async def get_meal_plans(
    week_start: str = Query(..., description="Week start date in YYYY-MM-DD format"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from datetime import date

    try:
        ws = date.fromisoformat(week_start)
    except ValueError:
        raise ValueError("week_start must be in YYYY-MM-DD format")

    week_end = ws + timedelta(days=6)

    query = (
        select(MealPlan)
        .where(MealPlan.date >= ws)
        .where(MealPlan.date <= week_end)
        .order_by(MealPlan.date, MealPlan.meal_type)
    )

    result = await db.execute(query)
    plans = result.scalars().all()

    return {
        "week_start": week_start,
        "week_end": str(week_end),
        "meals": [
            {
                "id": p.id,
                "meal_type": p.meal_type,
                "date": str(p.date),
                "recipe_id": p.recipe_id,
                "title": p.title,
                "notes": p.notes,
                "recipe": None,
                "created_at": str(p.created_at) if hasattr(p, 'created_at') and p.created_at else "",
                "updated_at": str(p.updated_at) if hasattr(p, 'updated_at') and p.updated_at else "",
            }
            for p in plans
        ],
    }
