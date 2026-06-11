from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.schemas.models import (
    ChoreCreate,
    ChoreUpdate,
    ChoreResponse,
    ChoreInstanceResponse,
    ChoreCompletionLogResponse,
    ChoreStatsResponse,
    ChoreQuickAdd,
)
from app.models import Chore, ChoreInstance, ChoreCompletionLog, User, UserStreak

router = APIRouter()


def _parse_recurrence_rule(rule: str) -> list[str]:
    """Generate due dates for a recurrence rule for the next 30 days."""
    dates = []
    today = datetime.now(timezone.utc).date()

    if rule == "daily":
        for i in range(30):
            dates.append((today + timedelta(days=i)).isoformat())
    elif rule.startswith("weekly_"):
        day_map = {
            "mon": 0, "tue": 1, "wed": 2, "thu": 3,
            "fri": 4, "sat": 5, "sun": 6,
        }
        target_day = day_map.get(rule[7:])
        if target_day is not None:
            for i in range(5):
                target = today + timedelta(days=(target_day - today.weekday() + 7 * i) % 7)
                dates.append(target.isoformat())
    elif rule.startswith("monthly_"):
        try:
            day = int(rule[8:])
            for i in range(3):
                target = today + relativedelta(day=day, months=i)
                if target >= today:
                    dates.append(target.isoformat())
        except (ValueError, IndexError):
            pass
    elif rule.startswith("every_") and "_days_" in rule:
        try:
            parts = rule.split("_")
            interval = int(parts[2])
            for i in range(0, 30, interval):
                dates.append((today + timedelta(days=i)).isoformat())
        except (IndexError, ValueError):
            pass

    return dates


@router.post("/templates", response_model=ChoreResponse, status_code=status.HTTP_201_CREATED)
async def create_chore_template(
    req: ChoreCreate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    template = Chore(
        title=req.title,
        description=req.description,
        assignment_mode=req.assignment_mode,
        recurrence_rule=req.recurrence_rule,
        default_assigned_to_id=req.default_assigned_to_id,
        point_value=req.point_value,
        created_by_id=admin["sub"],
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)

    return ChoreResponse(
        id=template.id,
        title=template.title,
        description=template.description,
        assignment_mode=template.assignment_mode,
        recurrence_rule=template.recurrence_rule,
        default_assigned_to_id=template.default_assigned_to_id,
        point_value=template.point_value,
        is_active=template.is_active,
        created_by_id=template.created_by_id,
        created_at=str(template.created_at),
        updated_at=str(template.updated_at),
    )


@router.get("/templates", response_model=list[ChoreResponse])
async def list_chore_templates(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    query = select(Chore).where(Chore.is_active == True).order_by(Chore.title)  # noqa: E712
    result = await db.execute(query)
    templates = result.scalars().all()

    return [
        ChoreResponse(
            id=t.id,
            title=t.title,
            description=t.description,
            assignment_mode=t.assignment_mode,
            recurrence_rule=t.recurrence_rule,
            default_assigned_to_id=t.default_assigned_to_id,
            point_value=t.point_value,
            is_active=t.is_active,
            created_by_id=t.created_by_id,
            created_at=str(t.created_at),
            updated_at=str(t.updated_at),
        )
        for t in templates
    ]


@router.patch("/templates/{template_id}", response_model=ChoreResponse)
async def update_chore_template(
    template_id: str,
    req: ChoreUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(Chore).where(Chore.id == template_id))
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chore template not found")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)

    await db.flush()
    await db.refresh(template)

    return ChoreResponse(
        id=template.id,
        title=template.title,
        description=template.description,
        assignment_mode=template.assignment_mode,
        recurrence_rule=template.recurrence_rule,
        default_assigned_to_id=template.default_assigned_to_id,
        point_value=template.point_value,
        is_active=template.is_active,
        created_by_id=template.created_by_id,
        created_at=str(template.created_at),
        updated_at=str(template.updated_at),
    )


@router.delete("/templates/{template_id}")
async def deactivate_chore_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(Chore).where(Chore.id == template_id))
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chore template not found")

    template.is_active = False
    await db.flush()

    return {"message": "Chore template deactivated"}


@router.get("/instances", response_model=list[ChoreInstanceResponse])
async def list_chore_instances(
    status_filter: Optional[str] = Query(None, description="Filter by status: pending, claimed, completed, expired"),
    due_date: Optional[str] = Query(None, description="Filter by due date (ISO format)"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["sub"]
    is_admin = current_user["role"] == "admin"

    query = select(ChoreInstance).where(ChoreInstance.status.in_(["pending", "claimed"]))

    if not is_admin:
        query = query.where(
            ChoreInstance.assigned_to_id == user_id | ChoreInstance.claimed_by_id == user_id
        )

    if status_filter:
        query = query.where(ChoreInstance.status == status_filter)
    if due_date:
        query = query.where(ChoreInstance.due_date == due_date)

    query = query.order_by(ChoreInstance.due_date, ChoreInstance.status)
    result = await db.execute(query)
    instances = result.scalars().all()

    return [
        ChoreInstanceResponse(
            id=i.id,
            chore_template_id=i.chore_template_id,
            assigned_to_id=i.assigned_to_id,
            due_date=i.due_date,
            status=i.status,
            claimed_by_id=i.claimed_by_id,
            claimed_at=str(i.claimed_at) if i.claimed_at else None,
            completed_by_id=i.completed_by_id,
            completed_at=str(i.completed_at) if i.completed_at else None,
            created_at=str(i.created_at),
        )
        for i in instances
    ]


@router.post("/quick-add", status_code=status.HTTP_201_CREATED)
async def quick_add_chore(
    req: ChoreQuickAdd,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == req.assigned_to_id, User.is_active == True))
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned user not found")

    template = Chore(
        title=req.title,
        description=req.description,
        assignment_mode="assigned",
        recurrence_rule=req.recurrence_rule,
        default_assigned_to_id=req.assigned_to_id,
        point_value=req.point_value,
        created_by_id=current_user["sub"],
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)

    today = datetime.now(timezone.utc).date()
    instances = []

    if req.recurrence_rule == "none":
        instance = ChoreInstance(
            chore_template_id=template.id,
            assigned_to_id=req.assigned_to_id,
            due_date=today.isoformat(),
            status="pending",
        )
        db.add(instance)
        instances.append(instance)
    else:
        all_dates = _parse_recurrence_rule(req.recurrence_rule)
        limit_date = today + timedelta(days=7)
        for date_str in all_dates:
            d = datetime.fromisoformat(date_str).date()
            if d <= limit_date:
                instance = ChoreInstance(
                    chore_template_id=template.id,
                    assigned_to_id=req.assigned_to_id,
                    due_date=date_str,
                    status="pending",
                )
                db.add(instance)
                instances.append(instance)

    await db.flush()

    template_response = ChoreResponse(
        id=template.id,
        title=template.title,
        description=template.description,
        assignment_mode=template.assignment_mode,
        recurrence_rule=template.recurrence_rule,
        default_assigned_to_id=template.default_assigned_to_id,
        point_value=template.point_value,
        is_active=template.is_active,
        created_by_id=template.created_by_id,
        created_at=str(template.created_at),
        updated_at=str(template.updated_at),
    )

    instances_response = [
        ChoreInstanceResponse(
            id=i.id,
            chore_template_id=i.chore_template_id,
            assigned_to_id=i.assigned_to_id,
            due_date=i.due_date,
            status=i.status,
            claimed_by_id=i.claimed_by_id,
            claimed_at=i.claimed_at,
            completed_by_id=i.completed_by_id,
            completed_at=i.completed_at,
            created_at=str(i.created_at),
        )
        for i in instances
    ]

    return {"template": template_response, "instances": instances_response}


@router.post("/instances/{instance_id}/claim", response_model=ChoreInstanceResponse)
async def claim_chore_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(ChoreInstance).where(ChoreInstance.id == instance_id))
    instance = result.scalar_one_or_none()

    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chore instance not found")

    if instance.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chore is not available to claim")

    # Check if already claimed by someone else
    if instance.claimed_by_id and instance.claimed_by_id != current_user["sub"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chore already claimed by another user")

    instance.status = "claimed"
    instance.claimed_by_id = current_user["sub"]
    instance.claimed_at = datetime.now(timezone.utc).isoformat()

    await db.flush()
    await db.refresh(instance)

    return ChoreInstanceResponse(
        id=instance.id,
        chore_template_id=instance.chore_template_id,
        assigned_to_id=instance.assigned_to_id,
        due_date=instance.due_date,
        status=instance.status,
        claimed_by_id=instance.claimed_by_id,
        claimed_at=str(instance.claimed_at) if instance.claimed_at else None,
        completed_by_id=instance.completed_by_id,
        completed_at=str(instance.completed_at) if instance.completed_at else None,
        created_at=str(instance.created_at),
    )


@router.post("/instances/{instance_id}/complete", response_model=ChoreInstanceResponse)
async def complete_chore_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(ChoreInstance).where(ChoreInstance.id == instance_id))
    instance = result.scalar_one_or_none()

    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chore instance not found")

    if instance.status not in ["pending", "claimed"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chore is not available to complete")

    # Check authorization: assigned user, claimed user, or admin
    is_assigned = instance.assigned_to_id == current_user["sub"]
    is_claimed_by_user = instance.claimed_by_id == current_user["sub"]
    is_admin = current_user["role"] == "admin"

    if not is_assigned and not is_claimed_by_user and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to complete this chore")

    # Get chore template for point value
    template_result = await db.execute(select(Chore).where(Chore.id == instance.chore_template_id))
    template = template_result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chore template not found")

    # Update instance
    instance.status = "completed"
    instance.completed_by_id = current_user["sub"]
    instance.completed_at = datetime.now(timezone.utc).isoformat()

    # Create completion log
    log_entry = ChoreCompletionLog(
        instance_id=instance.id,
        completed_by_id=current_user["sub"],
        completed_at=instance.completed_at,
        points_earned=template.point_value,
    )
    db.add(log_entry)

    await db.flush()
    await db.refresh(instance)

    return ChoreInstanceResponse(
        id=instance.id,
        chore_template_id=instance.chore_template_id,
        assigned_to_id=instance.assigned_to_id,
        due_date=instance.due_date,
        status=instance.status,
        claimed_by_id=instance.claimed_by_id,
        claimed_at=str(instance.claimed_at) if instance.claimed_at else None,
        completed_by_id=instance.completed_by_id,
        completed_at=str(instance.completed_at) if instance.completed_at else None,
        created_at=str(instance.created_at),
    )


@router.get("/completion-log", response_model=list[ChoreCompletionLogResponse])
async def get_completion_log(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    is_admin = current_user["role"] == "admin"

    query = select(ChoreCompletionLog).order_by(ChoreCompletionLog.completed_at.desc()).limit(limit)

    if not is_admin:
        query = query.where(ChoreCompletionLog.completed_by_id == current_user["sub"])

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        ChoreCompletionLogResponse(
            id=l.id,
            instance_id=l.instance_id,
            completed_by_id=l.completed_by_id,
            completed_at=str(l.completed_at),
            points_earned=l.points_earned,
        )
        for l in logs
    ]


@router.get("/stats", response_model=ChoreStatsResponse)
async def get_chore_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["sub"]

    # Total completed
    result = await db.execute(
        select(func.count()).select_from(ChoreCompletionLog).where(ChoreCompletionLog.completed_by_id == user_id)
    )
    total_completed = result.scalar() or 0

    # Points earned
    result = await db.execute(
        select(func.sum(ChoreCompletionLog.points_earned)).where(ChoreCompletionLog.completed_by_id == user_id)
    )
    points_earned = result.scalar() or 0

    # Current streak (from user_streaks table - will be populated by background job)
    result = await db.execute(select(UserStreak).where(UserStreak.user_id == user_id))
    streak = result.scalar_one_or_none()
    current_streak = streak.current_streak if streak else 0
    longest_streak = streak.longest_streak if streak else 0

    return ChoreStatsResponse(
        total_completed=total_completed,
        current_streak=current_streak,
        longest_streak=longest_streak,
        points_earned=points_earned,
    )
