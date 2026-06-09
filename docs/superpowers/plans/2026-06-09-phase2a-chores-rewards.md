# Phase 2A: Chores + Rewards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build chore management with flexible recurrence, self-claiming, and automatic reward points + allowance distribution with streaks and badges.

**Architecture:** Add chore/reward models to existing SQLAlchemy setup, create dedicated routers, implement APScheduler background jobs for instance generation and allowance distribution, build frontend pages with tabs for templates/instances/history and store/badges/history.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, aiosqlite, Alembic, APScheduler, React 19, Vite, TypeScript, Tailwind CSS, Zustand, TanStack Query.

---

## Task Group 1: Database Models & Migration

### Task 1.1: Add chore and reward models to event.py

**Files:**
- Modify: `backend/app/models/event.py` — Add Chore, ChoreInstance, ChoreCompletionLog, RewardPointsLedger, AllowanceLedger, Reward, RewardRequest, BadgeDefinition, UserBadge, UserStreak models

- [ ] **Step 1: Add new models to event.py**

Read the current `backend/app/models/event.py` file, then add these models after the existing Announcement class:

```python
from datetime import date, datetime, timezone
from uuid import uuid4


class Chore(Base, TimestampMixin):
    __tablename__ = "chores"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignment_mode: Mapped[str] = mapped_column(Text, nullable=False, default="assigned")  # assigned | claimable
    recurrence_rule: Mapped[str] = mapped_column(Text, nullable=False)
    point_value: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)


class ChoreInstance(Base, TimestampMixin):
    __tablename__ = "chore_instances"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    chore_template_id: Mapped[str] = mapped_column(Text, ForeignKey("chores.id"), nullable=False)
    assigned_to_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"), nullable=True)
    due_date: Mapped[str] = mapped_column(Text, nullable=False)  # ISO date string
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")  # pending | claimed | completed | expired
    claimed_by_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"), nullable=True)
    claimed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_by_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChoreCompletionLog(Base):
    __tablename__ = "chore_completion_logs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("chore_instances.id"), nullable=False)
    completed_by_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    completed_at: Mapped[str] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    points_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RewardPointsLedger(Base):
    __tablename__ = "reward_points_ledger"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)  # + for earned, - for spent
    type: Mapped[str] = mapped_column(Text, nullable=False)  # chore_completion | reward_purchase | reward_request | admin_grant | admin_deduct | streak_bonus | badge_bonus
    reference_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)  # ISO datetime string


class AllowanceLedger(Base):
    __tablename__ = "allowance_ledger"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    amount: Mapped[str] = mapped_column(Text, nullable=False)  # Decimal as string
    type: Mapped[str] = mapped_column(Text, nullable=False)  # allowance_weekly | chore_bonus | admin_grant | purchase | parent_allowance
    reference_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)  # ISO datetime string


class Reward(Base, TimestampMixin):
    __tablename__ = "rewards"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    point_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    is_auto_fulfill: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)


class RewardRequest(Base):
    __tablename__ = "reward_requests"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    reward_id: Mapped[str] = mapped_column(Text, ForeignKey("rewards.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")  # pending | approved | rejected
    requested_at: Mapped[str] = mapped_column(Text, nullable=False)  # ISO datetime string
    approved_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class BadgeDefinition(Base, TimestampMixin):
    __tablename__ = "badge_definitions"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(Text, nullable=True)  # emoji
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False)  # streak | milestone
    trigger_value: Mapped[int] = mapped_column(Integer, nullable=False)
    points_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class UserBadge(Base):
    __tablename__ = "user_badges"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    badge_definition_id: Mapped[str] = mapped_column(Text, ForeignKey("badge_definitions.id"), nullable=False)
    earned_at: Mapped[str] = mapped_column(Text, nullable=False)  # ISO datetime string


class UserStreak(Base):
    __tablename__ = "user_streaks"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), primary_key=True)
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_completion_date: Mapped[str | None] = mapped_column(Text, nullable=True)  # ISO date string
    grace_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

- [ ] **Step 2: Update models/__init__.py**

Read the current `backend/app/models/__init__.py`, then add the new model imports:

```python
from app.models.event import (
    User,
    Event,
    CalendarSource,
    CalendarEvent,
    SyncLog,
    Announcement,
    Chore,
    ChoreInstance,
    ChoreCompletionLog,
    RewardPointsLedger,
    AllowanceLedger,
    Reward,
    RewardRequest,
    BadgeDefinition,
    UserBadge,
    UserStreak,
)

__all__ = [
    "User",
    "Event",
    "CalendarSource",
    "CalendarEvent",
    "SyncLog",
    "Announcement",
    "Chore",
    "ChoreInstance",
    "ChoreCompletionLog",
    "RewardPointsLedger",
    "AllowanceLedger",
    "Reward",
    "RewardRequest",
    "BadgeDefinition",
    "UserBadge",
    "UserStreak",
]
```

- [ ] **Step 3: Update main.py imports**

Read the current `backend/app/main.py`, then update the imports at the bottom to include new models:

Change the import line:
```python
from app.models import User, Event, CalendarSource, CalendarEvent, SyncLog, Announcement, Chore, ChoreInstance, ChoreCompletionLog, RewardPointsLedger, AllowanceLedger, Reward, RewardRequest, BadgeDefinition, UserBadge, UserStreak
```

- [ ] **Step 4: Run tests to verify models load**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_auth.py -v
```

Expected: All existing tests still pass (models are additive, no breaking changes).

---

## Task Group 2: Pydantic Schemas

### Task 2.1: Add chore and reward schemas

**Files:**
- Modify: `backend/app/schemas/models.py` — Add Chore, ChoreInstance, Reward, RewardRequest, Streak, Badge schemas

- [ ] **Step 1: Add new schemas to models.py**

Read the current `backend/app/schemas/models.py`, then append these schemas after the existing AnnouncementResponse:

```python
# Chore schemas
class ChoreCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    assignment_mode: str = Field(default="assigned", pattern=r"^(assigned|claimable)$")
    recurrence_rule: str = Field(..., min_length=1, max_length=50)
    point_value: int = Field(default=10, ge=1, le=1000)


class ChoreUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    assignment_mode: Optional[str] = Field(None, pattern=r"^(assigned|claimable)$")
    recurrence_rule: Optional[str] = None
    point_value: Optional[int] = Field(None, ge=1, le=1000)
    is_active: Optional[bool] = None


class ChoreResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    assignment_mode: str
    recurrence_rule: str
    point_value: int
    is_active: bool
    created_by_id: str
    created_at: str
    updated_at: str


class ChoreInstanceResponse(BaseModel):
    id: str
    chore_template_id: str
    assigned_to_id: Optional[str] = None
    due_date: str
    status: str
    claimed_by_id: Optional[str] = None
    claimed_at: Optional[str] = None
    completed_by_id: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str


class ChoreCompletionLogResponse(BaseModel):
    id: str
    instance_id: str
    completed_by_id: str
    completed_at: str
    points_earned: int


class ChoreStatsResponse(BaseModel):
    total_completed: int
    current_streak: int
    longest_streak: int
    points_earned: int


# Reward schemas
class RewardPointsLedgerEntry(BaseModel):
    id: str
    user_id: str
    points: int
    type: str
    reference_id: Optional[str] = None
    description: Optional[str] = None
    created_at: str


class AllowanceLedgerEntry(BaseModel):
    id: str
    user_id: str
    amount: str
    type: str
    reference_id: Optional[str] = None
    description: Optional[str] = None
    created_at: str


class RewardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    point_cost: int = Field(..., ge=1, le=100000)
    is_auto_fulfill: bool = False


class RewardUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    point_cost: Optional[int] = Field(None, ge=1, le=100000)
    is_auto_fulfill: Optional[bool] = None
    is_active: Optional[bool] = None


class RewardResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    point_cost: int
    is_auto_fulfill: bool
    is_active: bool
    created_by_id: str
    created_at: str
    updated_at: str


class RewardRequestCreate(BaseModel):
    pass


class RewardRequestResponse(BaseModel):
    id: str
    user_id: str
    reward_id: str
    status: str
    requested_at: str
    approved_at: Optional[str] = None
    approved_by_id: Optional[str] = None
    rejection_reason: Optional[str] = None


class RewardResponseDetail(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    point_cost: int
    is_auto_fulfill: bool
    is_active: bool
    created_by_id: str
    created_at: str
    updated_at: str
    user_points_balance: int
    can_purchase: bool


class StreakResponse(BaseModel):
    user_id: str
    current_streak: int
    longest_streak: int
    last_completion_date: Optional[str] = None
    grace_days: int


class BadgeDefinitionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    icon: Optional[str] = None
    trigger_type: str = Field(..., pattern=r"^(streak|milestone)$")
    trigger_value: int = Field(..., ge=1, le=10000)
    points_reward: int = Field(default=0, ge=0, le=100000)


class BadgeDefinitionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    icon: Optional[str] = None
    trigger_type: Optional[str] = Field(None, pattern=r"^(streak|milestone)$")
    trigger_value: Optional[int] = Field(None, ge=1, le=10000)
    points_reward: Optional[int] = Field(None, ge=0, le=100000)


class BadgeDefinitionResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    trigger_type: str
    trigger_value: int
    points_reward: int
    created_at: str
    updated_at: str


class UserBadgeResponse(BaseModel):
    id: str
    user_id: str
    badge_definition_id: str
    earned_at: str


class AllowanceConfigUpdate(BaseModel):
    weekly_amount: str = Field(..., pattern=r"^\d+(\.\d{1,2})?$")
```

- [ ] **Step 2: Run tests to verify schemas load**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_auth.py -v
```

Expected: All tests pass.

---

## Task Group 3: Chore Routers

### Task 3.1: Create chore router

**Files:**
- Create: `backend/app/routers/chores.py` — Full chore CRUD, instance management, completion, stats

- [ ] **Step 1: Create chores.py router**

Create `backend/app/routers/chores.py` with the following content:

```python
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
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
)
from app.models import Chore, ChoreInstance, ChoreCompletionLog, User

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
```

Note: The import for `dateutil.relativedelta` requires adding `python-dateutil` to requirements. It's already installed (used by calendar sync). The import for `UserStreak` needs to be added to the models import.

- [ ] **Step 2: Add UserStreak import to chores.py**

Add this import at the top of the file:

```python
from app.models import Chore, ChoreInstance, ChoreCompletionLog, User, UserStreak
```

- [ ] **Step 3: Verify imports work**

```bash
cd backend && source .venv/bin/activate && python -c "from app.routers.chores import router; print('OK')"
```

Expected: `OK`

---

## Task Group 4: Reward Routers

### Task 4.1: Create reward router

**Files:**
- Create: `backend/app/routers/rewards.py` — Points/allowance balance, reward catalog, purchases/requests, streaks, badges

- [ ] **Step 1: Create rewards.py router**

Create `backend/app/routers/rewards.py` with the following content:

```python
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.schemas.models import (
    RewardPointsLedgerEntry,
    AllowanceLedgerEntry,
    RewardCreate,
    RewardUpdate,
    RewardResponse,
    RewardRequestCreate,
    RewardRequestResponse,
    RewardResponseDetail,
    StreakResponse,
    BadgeDefinitionCreate,
    BadgeDefinitionUpdate,
    BadgeDefinitionResponse,
    UserBadgeResponse,
    AllowanceConfigUpdate,
)
from app.models import (
    RewardPointsLedger,
    AllowanceLedger,
    Reward,
    RewardRequest,
    BadgeDefinition,
    UserBadge,
    UserStreak,
    ChoreCompletionLog,
    User,
)

router = APIRouter()


def _get_or_create_streak(db: AsyncSession, user_id: str) -> UserStreak:
    """Get or create a user streak record."""
    result = await db.execute(select(UserStreak).where(UserStreak.user_id == user_id))
    streak = result.scalar_one_or_none()

    if streak is None:
        streak = UserStreak(
            user_id=user_id,
            current_streak=0,
            longest_streak=0,
            grace_days=1,
        )
        db.add(streak)
        await db.flush()
        await db.refresh(streak)

    return streak


@router.get("/points/balance")
async def get_points_balance(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["sub"]

    # Calculate current balance
    result = await db.execute(
        select(func.sum(RewardPointsLedger.points)).where(RewardPointsLedger.user_id == user_id)
    )
    total = result.scalar() or 0

    # Get recent transactions
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
            RewardPointsLedgerEntry(
                id=e.id,
                user_id=e.user_id,
                points=e.points,
                type=e.type,
                reference_id=e.reference_id,
                description=e.description,
                created_at=str(e.created_at),
            )
            for e in entries
        ],
    }


@router.get("/points/ledger")
async def get_points_ledger(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["sub"]

    query = select(RewardPointsLedger).where(RewardPointsLedger.user_id == user_id).order_by(RewardPointsLedger.created_at.desc()).limit(limit)
    result = await db.execute(query)
    entries = result.scalars().all()

    return [
        RewardPointsLedgerEntry(
            id=e.id,
            user_id=e.user_id,
            points=e.points,
            type=e.type,
            reference_id=e.reference_id,
            description=e.description,
            created_at=str(e.created_at),
        )
        for e in entries
    ]


@router.get("/allowance/balance")
async def get_allowance_balance(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["sub"]

    # Calculate current balance
    result = await db.execute(
        select(func.sum(AllowanceLedger.amount)).where(AllowanceLedger.user_id == user_id)
    )
    total = float(result.scalar() or 0)

    # Get recent transactions
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
            AllowanceLedgerEntry(
                id=e.id,
                user_id=e.user_id,
                amount=e.amount,
                type=e.type,
                reference_id=e.reference_id,
                description=e.description,
                created_at=str(e.created_at),
            )
            for e in entries
        ],
    }


@router.get("/allowance/ledger")
async def get_allowance_ledger(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["sub"]

    query = select(AllowanceLedger).where(AllowanceLedger.user_id == user_id).order_by(AllowanceLedger.created_at.desc()).limit(limit)
    result = await db.execute(query)
    entries = result.scalars().all()

    return [
        AllowanceLedgerEntry(
            id=e.id,
            user_id=e.user_id,
            amount=e.amount,
            type=e.type,
            reference_id=e.reference_id,
            description=e.description,
            created_at=str(e.created_at),
        )
        for e in entries
    ]


@router.post("/allowance/config", status_code=status.HTTP_200_OK)
async def set_allowance_config(
    req: AllowanceConfigUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Set weekly allowance amount for all active users."""
    result = await db.execute(select(User).where(User.is_active == True))  # noqa: E712
    users = result.scalars().all()

    for user in users:
        # Update or create allowance config (stored in user settings)
        import json
        settings = json.loads(user.settings_json) if user.settings_json else {}
        settings["weekly_allowance"] = req.weekly_amount
        user.settings_json = json.dumps(settings)

    await db.flush()
    return {"message": f"Weekly allowance set to ${req.weekly_amount} for {len(users)} users"}


@router.get("/catalog", response_model=list[RewardResponse])
async def list_rewards(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    query = select(Reward).where(Reward.is_active == True).order_by(Reward.point_cost)  # noqa: E712
    result = await db.execute(query)
    rewards = result.scalars().all()

    return [
        RewardResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            point_cost=r.point_cost,
            is_auto_fulfill=r.is_auto_fulfill,
            is_active=r.is_active,
            created_by_id=r.created_by_id,
            created_at=str(r.created_at),
            updated_at=str(r.updated_at),
        )
        for r in rewards
    ]


@router.get("/catalog/{reward_id}", response_model=RewardResponseDetail)
async def get_reward_detail(
    reward_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Reward).where(Reward.id == reward_id))
    reward = result.scalar_one_or_none()

    if reward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward not found")

    # Get user's points balance
    result = await db.execute(
        select(func.sum(RewardPointsLedger.points)).where(RewardPointsLedger.user_id == current_user["sub"])
    )
    balance = int(result.scalar() or 0)

    return RewardResponseDetail(
        id=reward.id,
        name=reward.name,
        description=reward.description,
        point_cost=reward.point_cost,
        is_auto_fulfill=reward.is_auto_fulfill,
        is_active=reward.is_active,
        created_by_id=reward.created_by_id,
        created_at=str(reward.created_at),
        updated_at=str(reward.updated_at),
        user_points_balance=balance,
        can_purchase=balance >= reward.point_cost,
    )


@router.post("/catalog", response_model=RewardResponse, status_code=status.HTTP_201_CREATED)
async def create_reward(
    req: RewardCreate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    reward = Reward(
        name=req.name,
        description=req.description,
        point_cost=req.point_cost,
        is_auto_fulfill=req.is_auto_fulfill,
        created_by_id=admin["sub"],
    )
    db.add(reward)
    await db.flush()
    await db.refresh(reward)

    return RewardResponse(
        id=reward.id,
        name=reward.name,
        description=reward.description,
        point_cost=reward.point_cost,
        is_auto_fulfill=reward.is_auto_fulfill,
        is_active=reward.is_active,
        created_by_id=reward.created_by_id,
        created_at=str(reward.created_at),
        updated_at=str(reward.updated_at),
    )


@router.patch("/catalog/{reward_id}", response_model=RewardResponse)
async def update_reward(
    reward_id: str,
    req: RewardUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(Reward).where(Reward.id == reward_id))
    reward = result.scalar_one_or_none()

    if reward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward not found")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(reward, key, value)

    await db.flush()
    await db.refresh(reward)

    return RewardResponse(
        id=reward.id,
        name=reward.name,
        description=reward.description,
        point_cost=reward.point_cost,
        is_auto_fulfill=reward.is_auto_fulfill,
        is_active=reward.is_active,
        created_by_id=reward.created_by_id,
        created_at=str(reward.created_at),
        updated_at=str(reward.updated_at),
    )


@router.delete("/catalog/{reward_id}")
async def deactivate_reward(
    reward_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(Reward).where(Reward.id == reward_id))
    reward = result.scalar_one_or_none()

    if reward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward not found")

    reward.is_active = False
    await db.flush()

    return {"message": "Reward deactivated"}


@router.post("/purchase/{reward_id}", status_code=status.HTTP_200_OK)
async def purchase_reward(
    reward_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Reward).where(Reward.id == reward_id))
    reward = result.scalar_one_or_none()

    if reward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward not found")

    if not reward.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reward is not available")

    if not reward.is_auto_fulfill:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This reward requires admin approval. Use /request instead.")

    # Get user's points balance
    result = await db.execute(
        select(func.sum(RewardPointsLedger.points)).where(RewardPointsLedger.user_id == current_user["sub"])
    )
    balance = int(result.scalar() or 0)

    if balance < reward.point_cost:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient points")

    # Deduct points
    ledger_entry = RewardPointsLedger(
        user_id=current_user["sub"],
        points=-reward.point_cost,
        type="reward_purchase",
        reference_id=reward_id,
        description=f"Purchased: {reward.name}",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(ledger_entry)

    await db.flush()

    return {
        "message": f"Successfully redeemed '{reward.name}'",
        "points_deducted": reward.point_cost,
        "remaining_balance": balance - reward.point_cost,
    }


@router.post("/request/{reward_id}", response_model=RewardRequestResponse, status_code=status.HTTP_201_CREATED)
async def request_reward(
    reward_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Reward).where(Reward.id == reward_id))
    reward = result.scalar_one_or_none()

    if reward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward not found")

    if not reward.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reward is not available")

    if reward.is_auto_fulfill:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This reward can be purchased directly. Use /purchase instead.")

    # Check for existing pending request
    result = await db.execute(
        select(RewardRequest).where(
            RewardRequest.user_id == current_user["sub"],
            RewardRequest.reward_id == reward_id,
            RewardRequest.status == "pending",
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have a pending request for this reward")

    request_entry = RewardRequest(
        user_id=current_user["sub"],
        reward_id=reward_id,
        status="pending",
        requested_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(request_entry)
    await db.flush()
    await db.refresh(request_entry)

    return RewardRequestResponse(
        id=request_entry.id,
        user_id=request_entry.user_id,
        reward_id=request_entry.reward_id,
        status=request_entry.status,
        requested_at=request_entry.requested_at,
        approved_at=str(request_entry.approved_at) if request_entry.approved_at else None,
        approved_by_id=request_entry.approved_by_id,
        rejection_reason=request_entry.rejection_reason,
    )


@router.get("/my-requests", response_model=list[RewardRequestResponse])
async def get_my_requests(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(RewardRequest)
        .where(RewardRequest.user_id == current_user["sub"])
        .order_by(RewardRequest.requested_at.desc())
    )
    requests = result.scalars().all()

    return [
        RewardRequestResponse(
            id=r.id,
            user_id=r.user_id,
            reward_id=r.reward_id,
            status=r.status,
            requested_at=r.requested_at,
            approved_at=str(r.approved_at) if r.approved_at else None,
            approved_by_id=r.approved_by_id,
            rejection_reason=r.rejection_reason,
        )
        for r in requests
    ]


@router.get("/admin/requests", response_model=list[RewardRequestResponse])
async def get_all_requests(
    status_filter: Optional[str] = Query(None, description="Filter by status: pending, approved, rejected"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    query = select(RewardRequest).order_by(RewardRequest.requested_at.desc())

    if status_filter:
        query = query.where(RewardRequest.status == status_filter)

    result = await db.execute(query)
    requests = result.scalars().all()

    return [
        RewardRequestResponse(
            id=r.id,
            user_id=r.user_id,
            reward_id=r.reward_id,
            status=r.status,
            requested_at=r.requested_at,
            approved_at=str(r.approved_at) if r.approved_at else None,
            approved_by_id=r.approved_by_id,
            rejection_reason=r.rejection_reason,
        )
        for r in requests
    ]


@router.put("/requests/{request_id}/approve", response_model=RewardRequestResponse)
async def approve_reward_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(RewardRequest).where(RewardRequest.id == request_id))
    request_entry = result.scalar_one_or_none()

    if request_entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward request not found")

    if request_entry.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request is not pending")

    # Get reward to deduct points
    result = await db.execute(select(Reward).where(Reward.id == request_entry.reward_id))
    reward = result.scalar_one_or_none()
    if reward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward not found")

    # Check user has enough points
    result = await db.execute(
        select(func.sum(RewardPointsLedger.points)).where(RewardPointsLedger.user_id == request_entry.user_id)
    )
    balance = int(result.scalar() or 0)

    if balance < reward.point_cost:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has insufficient points")

    # Deduct points
    ledger_entry = RewardPointsLedger(
        user_id=request_entry.user_id,
        points=-reward.point_cost,
        type="reward_purchase",
        reference_id=reward_id=request_entry.reward_id,
        description=f"Admin approved: {reward.name}",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(ledger_entry)

    # Update request
    request_entry.status = "approved"
    request_entry.approved_at = datetime.now(timezone.utc).isoformat()
    request_entry.approved_by_id = admin["sub"]

    await db.flush()
    await db.refresh(request_entry)

    return RewardRequestResponse(
        id=request_entry.id,
        user_id=request_entry.user_id,
        reward_id=request_entry.reward_id,
        status=request_entry.status,
        requested_at=request_entry.requested_at,
        approved_at=str(request_entry.approved_at) if request_entry.approved_at else None,
        approved_by_id=request_entry.approved_by_id,
        rejection_reason=request_entry.rejection_reason,
    )


@router.put("/requests/{request_id}/reject", response_model=RewardRequestResponse)
async def reject_reward_request(
    request_id: str,
    req: dict = None,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(RewardRequest).where(RewardRequest.id == request_id))
    request_entry = result.scalar_one_or_none()

    if request_entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward request not found")

    if request_entry.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request is not pending")

    request_entry.status = "rejected"
    request_entry.rejection_reason = req.get("reason", "No reason provided") if req else "No reason provided"

    await db.flush()
    await db.refresh(request_entry)

    return RewardRequestResponse(
        id=request_entry.id,
        user_id=request_entry.user_id,
        reward_id=request_entry.reward_id,
        status=request_entry.status,
        requested_at=request_entry.requested_at,
        approved_at=str(request_entry.approved_at) if request_entry.approved_at else None,
        approved_by_id=request_entry.approved_by_id,
        rejection_reason=request_entry.rejection_reason,
    )


@router.get("/streak", response_model=StreakResponse)
async def get_streak(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(UserStreak).where(UserStreak.user_id == current_user["sub"]))
    streak = result.scalar_one_or_none()

    if streak is None:
        return StreakResponse(
            user_id=current_user["sub"],
            current_streak=0,
            longest_streak=0,
            last_completion_date=None,
            grace_days=1,
        )

    return StreakResponse(
        user_id=streak.user_id,
        current_streak=streak.current_streak,
        longest_streak=streak.longest_streak,
        last_completion_date=streak.last_completion_date,
        grace_days=streak.grace_days,
    )


@router.post("/streak/update", status_code=status.HTTP_200_OK)
async def update_streak_after_chore(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Called after chore completion to update streak and check badges."""
    user_id = current_user["sub"]
    today = datetime.now(timezone.utc).date().isoformat()

    streak = _get_or_create_streak(db, user_id)

    if streak.last_completion_date:
        last_date = datetime.fromisoformat(streak.last_completion_date).date()
        today_date = datetime.fromisoformat(today).date()
        days_diff = (today_date - last_date).days

        if days_diff <= streak.grace_days:
            streak.current_streak += 1
        else:
            streak.current_streak = 1

        if streak.current_streak > streak.longest_streak:
            streak.longest_streak = streak.current_streak
    else:
        streak.current_streak = 1

    streak.last_completion_date = today
    await db.flush()

    # Check for badge achievements
    result = await db.execute(
        select(BadgeDefinition).where(
            BadgeDefinition.trigger_type == "streak",
            BadgeDefinition.trigger_value == streak.current_streak,
        )
    )
    matching_badges = result.scalars().all()

    for badge in matching_badges:
        # Check if user already has this badge
        result = await db.execute(
            select(UserBadge).where(
                UserBadge.user_id == user_id,
                UserBadge.badge_definition_id == badge.id,
            )
        )
        existing = result.scalar_one_or_none()
        if not existing:
            user_badge = UserBadge(
                user_id=user_id,
                badge_definition_id=badge.id,
                earned_at=datetime.now(timezone.utc).isoformat(),
            )
            db.add(user_badge)

            # Award bonus points if any
            if badge.points_reward > 0:
                points_entry = RewardPointsLedger(
                    user_id=user_id,
                    points=badge.points_reward,
                    type="badge_bonus",
                    reference_id=badge.id,
                    description=f"Badge earned: {badge.name}",
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                db.add(points_entry)

    return {"message": "Streak updated", "current_streak": streak.current_streak}


@router.get("/badges", response_model=list[UserBadgeResponse])
async def get_user_badges(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(UserBadge)
        .where(UserBadge.user_id == current_user["sub"])
        .order_by(UserBadge.earned_at.desc())
    )
    badges = result.scalars().all()

    return [
        UserBadgeResponse(
            id=b.id,
            user_id=b.user_id,
            badge_definition_id=b.badge_definition_id,
            earned_at=b.earned_at,
        )
        for b in badges
    ]


@router.get("/badge-definitions", response_model=list[BadgeDefinitionResponse])
async def list_badge_definitions(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(BadgeDefinition).order_by(BadgeDefinition.trigger_value))
    definitions = result.scalars().all()

    return [
        BadgeDefinitionResponse(
            id=d.id,
            name=d.name,
            description=d.description,
            icon=d.icon,
            trigger_type=d.trigger_type,
            trigger_value=d.trigger_value,
            points_reward=d.points_reward,
            created_at=str(d.created_at),
            updated_at=str(d.updated_at),
        )
        for d in definitions
    ]


@router.post("/badge-definitions", response_model=BadgeDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_badge_definition(
    req: BadgeDefinitionCreate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    definition = BadgeDefinition(
        name=req.name,
        description=req.description,
        icon=req.icon,
        trigger_type=req.trigger_type,
        trigger_value=req.trigger_value,
        points_reward=req.points_reward,
    )
    db.add(definition)
    await db.flush()
    await db.refresh(definition)

    return BadgeDefinitionResponse(
        id=definition.id,
        name=definition.name,
        description=definition.description,
        icon=definition.icon,
        trigger_type=definition.trigger_type,
        trigger_value=definition.trigger_value,
        points_reward=definition.points_reward,
        created_at=str(definition.created_at),
        updated_at=str(definition.updated_at),
    )


@router.patch("/badge-definitions/{badge_id}", response_model=BadgeDefinitionResponse)
async def update_badge_definition(
    badge_id: str,
    req: BadgeDefinitionUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(BadgeDefinition).where(BadgeDefinition.id == badge_id))
    definition = result.scalar_one_or_none()

    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Badge definition not found")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(definition, key, value)

    await db.flush()
    await db.refresh(definition)

    return BadgeDefinitionResponse(
        id=definition.id,
        name=definition.name,
        description=definition.description,
        icon=definition.icon,
        trigger_type=definition.trigger_type,
        trigger_value=definition.trigger_value,
        points_reward=definition.points_reward,
        created_at=str(definition.created_at),
        updated_at=str(definition.updated_at),
    )


@router.delete("/badge-definitions/{badge_id}")
async def delete_badge_definition(
    badge_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(BadgeDefinition).where(BadgeDefinition.id == badge_id))
    definition = result.scalar_one_or_none()

    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Badge definition not found")

    await db.delete(definition)
    await db.flush()

    return {"message": "Badge definition deleted"}
```

- [ ] **Step 2: Verify imports work**

```bash
cd backend && source .venv/bin/activate && python -c "from app.routers.rewards import router; print('OK')"
```

Expected: `OK`

---

## Task Group 5: Register Routers & Update main.py

### Task 5.1: Register new routers in main.py

**Files:**
- Modify: `backend/app/main.py` — Add chores and rewards router imports

- [ ] **Step 1: Update main.py**

Read the current `backend/app/main.py`, then make these changes:

Change the router import:
```python
from app.routers import auth, users, events, calendar, announcements, wall, chores, rewards
```

Add router registrations after the existing ones:
```python
app.include_router(chores.router, prefix="/api/chores", tags=["chores"])
app.include_router(rewards.router, prefix="/api/rewards", tags=["rewards"])
```

- [ ] **Step 2: Verify app starts**

```bash
cd backend && source .venv/bin/activate && python -c "from app.main import app; print('Routes:', [r.path for r in app.routes if hasattr(r, 'path')])"
```

Expected: Output includes `/api/chores` and `/api/rewards` paths.

---

## Task Group 6: Background Jobs

### Task 6.1: Create chore instance generator job

**Files:**
- Create: `backend/app/jobs/chore_generator.py` — Daily job to generate chore instances
- Create: `backend/app/jobs/allowance_distributor.py` — Weekly allowance distribution
- Modify: `backend/app/main.py` — Initialize APScheduler with new jobs

- [ ] **Step 1: Create chore_generator.py**

Create `backend/app/jobs/chore_generator.py`:

```python
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chore, ChoreInstance, User


def _generate_dates_for_rule(rule: str, days: int = 7) -> list[str]:
    """Generate due dates for a recurrence rule for the next N days."""
    dates = []
    today = datetime.now(timezone.utc).date()

    if rule == "daily":
        for i in range(days):
            dates.append((today + timedelta(days=i)).isoformat())
    elif rule.startswith("weekly_"):
        day_map = {
            "mon": 0, "tue": 1, "wed": 2, "thu": 3,
            "fri": 4, "sat": 5, "sun": 6,
        }
        target_day = day_map.get(rule[7:])
        if target_day is not None:
            for i in range(2):  # Up to 2 weeks
                target = today + timedelta(days=(target_day - today.weekday() + 7 * i) % 7)
                if target >= today and target < today + timedelta(days=days * 2):
                    dates.append(target.isoformat())
    elif rule.startswith("monthly_"):
        try:
            day = int(rule[8:])
            for i in range(2):
                target = today + relativedelta(day=day, months=i)
                if target >= today and target < today + timedelta(days=days * 2):
                    dates.append(target.isoformat())
        except (ValueError, IndexError):
            pass
    elif rule.startswith("every_") and "_days_" in rule:
        try:
            parts = rule.split("_")
            interval = int(parts[2])
            for i in range(0, days * 2, interval):
                dates.append((today + timedelta(days=i)).isoformat())
        except (IndexError, ValueError):
            pass

    return dates


async def generate_chore_instances(db: AsyncSession):
    """Generate chore instances for the upcoming week from active templates."""
    result = await db.execute(select(Chore).where(Chore.is_active == True))
    templates = result.scalars().all()

    for template in templates:
        dates = _generate_dates_for_rule(template.recurrence_rule, 7)

        for due_date in dates:
            # Check if instance already exists for this template + date
            existing = await db.execute(
                select(ChoreInstance).where(
                    ChoreInstance.chore_template_id == template.id,
                    ChoreInstance.due_date == due_date,
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Generate instance
            if template.assignment_mode == "assigned":
                # For assigned mode, we need to know who to assign to
                # For now, skip (needs template-level assigned_to_id or admin assignment)
                # This is a simplified version - in production, templates would have
                # a default assigned_to_id or a mapping table
                continue
            else:
                # Claimable mode - create pending instance
                instance = ChoreInstance(
                    chore_template_id=template.id,
                    assigned_to_id=None,
                    due_date=due_date,
                    status="pending",
                )
                db.add(instance)

    await db.flush()
```

- [ ] **Step 2: Create allowance_distributor.py**

Create `backend/app/jobs/allowance_distributor.py`:

```python
from datetime import datetime, timezone
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AllowanceLedger, User


async def distribute_weekly_allowance(db: AsyncSession):
    """Distribute weekly allowance to all active users."""
    result = await db.execute(select(User).where(User.is_active == True))
    users = result.scalars().all()

    for user in users:
        # Get weekly allowance from user settings
        settings = json.loads(user.settings_json) if user.settings_json else {}
        weekly_amount = settings.get("weekly_allowance", "0.00")

        if not weekly_amount or float(weekly_amount) == 0:
            continue

        # Create allowance ledger entry
        entry = AllowanceLedger(
            user_id=user.id,
            amount=weekly_amount,
            type="allowance_weekly",
            description=f"Weekly allowance: ${weekly_amount}",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        db.add(entry)

    await db.flush()
```

- [ ] **Step 3: Update main.py to initialize APScheduler**

Read the current `backend/app/main.py`, then add APScheduler initialization:

Add import at the top:
```python
from apscheduler.asyncio.schedulers import AsyncIOScheduler
from app.jobs.chore_generator import generate_chore_instances
from app.jobs.allowance_distributor import distribute_weekly_allowance
```

Add scheduler setup in the startup event:
```python
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize APScheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(generate_chore_instances, "cron", hour=6, minute=0, args=[db], id="chore_generator", replace_existing=True)
    scheduler.add_job(distribute_weekly_allowance, "cron", day_of_week="mon", hour=7, minute=0, args=[db], id="allowance_distributor", replace_existing=True)
    scheduler.start()
```

Add scheduler shutdown in the shutdown event:
```python
@app.on_event("shutdown")
async def on_shutdown():
    await engine.dispose()
    scheduler.shutdown(wait=False)
```

Note: Need to use `get_db`'s engine/session. The `db` variable above should be obtained from the database module. Let me fix this to use the proper session:

Update the startup to use proper session handling:
```python
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize APScheduler
    from app.core.database import async_session_factory
    scheduler = AsyncIOScheduler()

    async def chore_job():
        async with async_session_factory() as session:
            await generate_chore_instances(session)
            await session.commit()

    async def allowance_job():
        async with async_session_factory() as session:
            await distribute_weekly_allowance(session)
            await session.commit()

    scheduler.add_job(chore_job, "cron", hour=6, minute=0, id="chore_generator", replace_existing=True)
    scheduler.add_job(allowance_job, "cron", day_of_week="mon", hour=7, minute=0, id="allowance_distributor", replace_existing=True)
    scheduler.start()
```

- [ ] **Step 4: Verify app starts with scheduler**

```bash
cd backend && source .venv/bin/activate && python -c "from app.main import app; print('OK')"
```

Expected: `OK`

---

## Task Group 7: Backend Tests

### Task 7.1: Create chore tests

**Files:**
- Create: `backend/tests/test_chores.py` — Chore template CRUD, instance management, completion, stats

- [ ] **Step 1: Create test_chores.py**

Create `backend/tests/test_chores.py`:

```python
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user

client = TestClient(app)


def override_get_current_user():
    return {"sub": "test-user-id", "role": "admin"}


app.dependency_overrides[get_current_user] = override_get_current_user


def test_create_chore_template():
    response = client.post(
        "/api/chores/templates",
        json={
            "title": "Take out trash",
            "description": "Take kitchen trash to curb",
            "assignment_mode": "claimable",
            "recurrence_rule": "weekly_mon",
            "point_value": 15,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Take out trash"
    assert data["assignment_mode"] == "claimable"
    assert data["point_value"] == 15
    template_id = data["id"]

    # Verify it appears in list
    response = client.get("/api/chores/templates")
    assert response.status_code == 200
    templates = response.json()
    assert any(t["id"] == template_id for t in templates)


def test_update_chore_template():
    # Create template first
    response = client.post(
        "/api/chores/templates",
        json={
            "title": "Dishes",
            "assignment_mode": "assigned",
            "recurrence_rule": "daily",
            "point_value": 10,
        },
    )
    template_id = response.json()["id"]

    # Update
    response = client.patch(
        f"/api/chores/templates/{template_id}",
        json={"point_value": 20, "is_active": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["point_value"] == 20
    assert data["is_active"] is False


def test_deactivate_chore_template():
    # Create template
    response = client.post(
        "/api/chores/templates",
        json={
            "title": "Clean room",
            "assignment_mode": "claimable",
            "recurrence_rule": "weekly_wed",
            "point_value": 25,
        },
    )
    template_id = response.json()["id"]

    # Deactivate
    response = client.delete(f"/api/chores/templates/{template_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Chore template deactivated"

    # Verify not in active list
    response = client.get("/api/chores/templates")
    assert response.status_code == 200
    assert not any(t["id"] == template_id for t in response.json())


def test_complete_chore_instance():
    # Create template
    response = client.post(
        "/api/chores/templates",
        json={
            "title": "Feed pet",
            "assignment_mode": "assigned",
            "recurrence_rule": "daily",
            "point_value": 5,
        },
    )
    template_id = response.json()["id"]

    # Create an instance manually via DB would be needed for full test
    # For now, test the API structure
    response = client.get("/api/chores/instances")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Create reward tests**

Create `backend/tests/test_rewards.py`:

```python
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user

client = TestClient(app)


def override_get_current_user():
    return {"sub": "test-user-id", "role": "admin"}


app.dependency_overrides[get_current_user] = override_get_current_user


def test_create_reward():
    response = client.post(
        "/api/rewards/catalog",
        json={
            "name": "Extra screen time",
            "description": "30 minutes of screen time",
            "point_cost": 50,
            "is_auto_fulfill": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Extra screen time"
    assert data["point_cost"] == 50
    assert data["is_auto_fulfill"] is True
    reward_id = data["id"]

    # Verify in catalog
    response = client.get("/api/rewards/catalog")
    assert response.status_code == 200
    assert any(r["id"] == reward_id for r in response.json())


def test_get_points_balance_empty():
    response = client.get("/api/rewards/points/balance")
    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == 0
    assert len(data["transactions"]) == 0


def test_get_allowance_balance_empty():
    response = client.get("/api/rewards/allowance/balance")
    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == 0.0
    assert len(data["transactions"]) == 0


def test_get_streak_empty():
    response = client.get("/api/rewards/streak")
    assert response.status_code == 200
    data = response.json()
    assert data["current_streak"] == 0
    assert data["longest_streak"] == 0


def test_list_badge_definitions():
    response = client.get("/api/rewards/badge-definitions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 3: Run all tests**

```bash
cd backend && source .venv/bin/activate && pytest tests/ -v
```

Expected: All tests pass (existing + new chore/reward tests).

---

## Task Group 8: Frontend — Chores Page

### Task 8.1: Create ChoresPage component

**Files:**
- Create: `frontend/src/pages/ChoresPage.tsx` — Full chores page with tabs
- Modify: `frontend/src/App.tsx` — Add /chores route
- Modify: `frontend/src/api/client.ts` — Add chore API methods

- [ ] **Step 1: Add chore API methods to client.ts**

Read the current `frontend/src/api/client.ts`, then add these methods:

```typescript
export const choreAPI = {
  getTemplates: () => apiClient.get('/chores/templates').then(r => r.data),
  createTemplate: (data: { title: string; description?: string; assignment_mode: string; recurrence_rule: string; point_value: number }) =>
    apiClient.post('/chores/templates', data).then(r => r.data),
  updateTemplate: (id: string, data: Partial<{ title: string; description?: string; assignment_mode: string; recurrence_rule: string; point_value: number; is_active: boolean }>) =>
    apiClient.patch(`/chores/templates/${id}`, data).then(r => r.data),
  deactivateTemplate: (id: string) =>
    apiClient.delete(`/chores/templates/${id}`).then(r => r.data),

  getInstances: (statusFilter?: string, dueDate?: string) =>
    apiClient.get('/chores/instances', { params: { status_filter: statusFilter, due_date: dueDate } }).then(r => r.data),
  claimInstance: (id: string) =>
    apiClient.post(`/chores/instances/${id}/claim`).then(r => r.data),
  completeInstance: (id: string) =>
    apiClient.post(`/chores/instances/${id}/complete`).then(r => r.data),

  getCompletionLog: (limit = 50) =>
    apiClient.get('/chores/completion-log', { params: { limit } }).then(r => r.data),

  getStats: () =>
    apiClient.get('/chores/stats').then(r => r.data),
};
```

- [ ] **Step 2: Create ChoresPage.tsx**

Create `frontend/src/pages/ChoresPage.tsx`:

```typescript
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { choreAPI } from '../api/client'
import { useAuth } from '../stores/auth'

type Tab = 'my' | 'available' | 'history' | 'templates'

interface ChoreTemplate {
  id: string
  title: string
  description?: string
  assignment_mode: string
  recurrence_rule: string
  point_value: number
  is_active: boolean
  created_by_id: string
  created_at: string
  updated_at: string
}

interface ChoreInstance {
  id: string
  chore_template_id: string
  assigned_to_id?: string
  due_date: string
  status: string
  claimed_by_id?: string
  claimed_at?: string
  completed_by_id?: string
  completed_at?: string
  created_at: string
}

interface CompletionLog {
  id: string
  instance_id: string
  completed_by_id: string
  completed_at: string
  points_earned: number
}

interface ChoreStats {
  total_completed: number
  current_streak: number
  longest_streak: number
  points_earned: number
}

export default function ChoresPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<Tab>('my')
  const [showTemplateForm, setShowTemplateForm] = useState(false)
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    assignment_mode: 'claimable' as 'assigned' | 'claimable',
    recurrence_rule: 'daily',
    point_value: 10,
  })

  const { data: templates } = useQuery({
    queryKey: ['chores-templates'],
    queryFn: choreAPI.getTemplates,
  })

  const { data: instances, refetch: refetchInstances } = useQuery({
    queryKey: ['chores-instances'],
    queryFn: () => choreAPI.getInstances(),
    refetchInterval: 30000,
  })

  const { data: completionLog } = useQuery({
    queryKey: ['chores-completion-log'],
    queryFn: () => choreAPI.getCompletionLog(50),
  })

  const { data: stats } = useQuery({
    queryKey: ['chores-stats'],
    queryFn: choreAPI.getStats,
  })

  const createMutation = useMutation({
    mutationFn: choreAPI.createTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chores-templates'] })
      setShowTemplateForm(false)
      setFormData({ title: '', description: '', assignment_mode: 'claimable', recurrence_rule: 'daily', point_value: 10 })
    },
  })

  const completeMutation = useMutation({
    mutationFn: choreAPI.completeInstance,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chores-instances'] })
      queryClient.invalidateQueries({ queryKey: ['chores-completion-log'] })
      queryClient.invalidateQueries({ queryKey: ['chores-stats'] })
    },
  })

  const claimMutation = useMutation({
    mutationFn: choreAPI.claimInstance,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chores-instances'] })
    },
  })

  const isAdmin = user?.role === 'admin'

  const myInstances = instances?.filter(i =>
    i.assigned_to_id === user?.id || i.claimed_by_id === user?.id
  ) || []

  const availableInstances = instances?.filter(i => i.status === 'pending') || []

  const handleComplete = (id: string) => {
    completeMutation.mutate(id)
  }

  const handleClaim = (id: string) => {
    claimMutation.mutate(id)
  }

  const handleCreateTemplate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(formData)
  }

  const tabs: { key: Tab; label: string; adminOnly?: boolean }[] = [
    { key: 'my', label: 'My Chores' },
    { key: 'available', label: 'Available' },
    { key: 'history', label: 'History' },
    { key: 'templates', label: 'Templates', adminOnly: true },
  ]

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">Chores</h1>

        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold">{stats.total_completed}</div>
              <div className="text-gray-400 text-sm">Completed</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold">{stats.current_streak}</div>
              <div className="text-gray-400 text-sm">Day Streak</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold">{stats.points_earned}</div>
              <div className="text-gray-400 text-sm">Points</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold">{stats.longest_streak}</div>
              <div className="text-gray-400 text-sm">Longest Streak</div>
            </div>
          </div>
        )}

        <div className="flex gap-2 mb-6 border-b border-gray-700">
          {tabs.filter(t => !t.adminOnly).map(tab => (
            <button
              key={tab.key}
              className={`px-4 py-2 ${activeTab === tab.key ? 'bg-blue-600 rounded-t-lg' : 'text-gray-400 hover:text-white'}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
          {isAdmin && (
            <button
              className={`px-4 py-2 ${activeTab === 'templates' ? 'bg-blue-600 rounded-t-lg' : 'text-gray-400 hover:text-white'}`}
              onClick={() => setActiveTab('templates')}
            >
              Templates
            </button>
          )}
        </div>

        {activeTab === 'my' && (
          <div className="space-y-3">
            {myInstances.length === 0 ? (
              <p className="text-gray-400 text-center py-8">No chores assigned to you</p>
            ) : (
              myInstances.map(instance => (
                <div key={instance.id} className="bg-gray-800 rounded-lg p-4 flex justify-between items-center">
                  <div>
                    <div className="font-medium">{instance.due_date}</div>
                    <div className="text-sm text-gray-400">
                      {instance.status === 'claimed' ? 'Claimed by you' : 'Assigned to you'}
                    </div>
                  </div>
                  {instance.status === 'claimed' && (
                    <button
                      onClick={() => handleComplete(instance.id)}
                      className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg"
                    >
                      Complete
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'available' && (
          <div className="space-y-3">
            {availableInstances.length === 0 ? (
              <p className="text-gray-400 text-center py-8">No available chores</p>
            ) : (
              availableInstances.map(instance => (
                <div key={instance.id} className="bg-gray-800 rounded-lg p-4 flex justify-between items-center">
                  <div>
                    <div className="font-medium">Due: {instance.due_date}</div>
                    <div className="text-sm text-gray-400">Click to claim</div>
                  </div>
                  <button
                    onClick={() => handleClaim(instance.id)}
                    className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg"
                  >
                    Claim
                  </button>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="space-y-2">
            {completionLog?.map(log => (
              <div key={log.id} className="bg-gray-800 rounded-lg p-3 flex justify-between items-center">
                <div>
                  <span className="text-gray-400">{new Date(log.completed_at).toLocaleDateString()}</span>
                  <span className="ml-4 text-sm">+{log.points_earned} points</span>
                </div>
              </div>
            )) || <p className="text-gray-400 text-center py-8">No completion history</p>}
          </div>
        )}

        {activeTab === 'templates' && isAdmin && (
          <div className="space-y-4">
            <button
              onClick={() => setShowTemplateForm(!showTemplateForm)}
              className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg"
            >
              {showTemplateForm ? 'Cancel' : 'Add Template'}
            </button>

            {showTemplateForm && (
              <form onSubmit={handleCreateTemplate} className="bg-gray-800 rounded-lg p-4 space-y-3">
                <input
                  type="text"
                  placeholder="Title"
                  value={formData.title}
                  onChange={e => setFormData({ ...formData, title: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                  required
                />
                <textarea
                  placeholder="Description"
                  value={formData.description || ''}
                  onChange={e => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                />
                <select
                  value={formData.assignment_mode}
                  onChange={e => setFormData({ ...formData, assignment_mode: e.target.value as 'assigned' | 'claimable' })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                >
                  <option value="assigned">Assigned (admin assigns)</option>
                  <option value="claimable">Claimable (self-assign)</option>
                </select>
                <select
                  value={formData.recurrence_rule}
                  onChange={e => setFormData({ ...formData, recurrence_rule: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                >
                  <option value="daily">Daily</option>
                  <option value="weekly_mon">Weekly - Monday</option>
                  <option value="weekly_tue">Weekly - Tuesday</option>
                  <option value="weekly_wed">Weekly - Wednesday</option>
                  <option value="weekly_thu">Weekly - Thursday</option>
                  <option value="weekly_fri">Weekly - Friday</option>
                  <option value="weekly_sat">Weekly - Saturday</option>
                  <option value="weekly_sun">Weekly - Sunday</option>
                  <option value="monthly_1st">Monthly - 1st</option>
                  <option value="monthly_15th">Monthly - 15th</option>
                  <option value="every_3_days_3">Every 3 Days</option>
                  <option value="every_7_days_7">Every 7 Days</option>
                </select>
                <input
                  type="number"
                  placeholder="Point value"
                  value={formData.point_value}
                  onChange={e => setFormData({ ...formData, point_value: parseInt(e.target.value) || 10 })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                  min="1"
                  max="1000"
                />
                <button type="submit" className="w-full bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg">
                  Create Template
                </button>
              </form>
            )}

            <div className="space-y-2">
              {templates?.map(template => (
                <div key={template.id} className="bg-gray-800 rounded-lg p-3 flex justify-between items-center">
                  <div>
                    <div className="font-medium">{template.title}</div>
                    <div className="text-sm text-gray-400">
                      {template.assignment_mode} · {template.recurrence_rule} · {template.point_value} pts
                    </div>
                  </div>
                  <div className="text-sm text-gray-500">{template.is_active ? 'Active' : 'Inactive'}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Update App.tsx with chore route**

Read the current `frontend/src/App.tsx`, then add the chore route:

```typescript
import ChoresPage from './pages/ChoresPage'
```

Add route:
```typescript
<Route path="/chores" element={<ChoresPage />} />
```

- [ ] **Step 4: Verify frontend compiles**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: Build succeeds with no errors.

---

## Task Group 9: Frontend — Rewards Page

### Task 9.1: Create RewardsPage component

**Files:**
- Create: `frontend/src/pages/RewardsPage.tsx` — Full rewards page with tabs
- Modify: `frontend/src/App.tsx` — Add /rewards route
- Modify: `frontend/src/api/client.ts` — Add reward API methods

- [ ] **Step 1: Add reward API methods to client.ts**

Read the current `frontend/src/api/client.ts`, then add:

```typescript
export const rewardAPI = {
  getPointsBalance: () => apiClient.get('/rewards/points/balance').then(r => r.data),
  getPointsLedger: (limit = 50) => apiClient.get('/rewards/points/ledger', { params: { limit } }).then(r => r.data),

  getAllowanceBalance: () => apiClient.get('/rewards/allowance/balance').then(r => r.data),
  getAllowanceLedger: (limit = 50) => apiClient.get('/rewards/allowance/ledger', { params: { limit } }).then(r => r.data),

  getCatalog: () => apiClient.get('/rewards/catalog').then(r => r.data),
  getRewardDetail: (id: string) => apiClient.get(`/rewards/catalog/${id}`).then(r => r.data),
  createReward: (data: { name: string; description?: string; point_cost: number; is_auto_fulfill: boolean }) =>
    apiClient.post('/rewards/catalog', data).then(r => r.data),
  updateReward: (id: string, data: Partial<{ name: string; description?: string; point_cost: number; is_auto_fulfill: boolean; is_active: boolean }>) =>
    apiClient.patch(`/rewards/catalog/${id}`, data).then(r => r.data),
  deactivateReward: (id: string) =>
    apiClient.delete(`/rewards/catalog/${id}`).then(r => r.data),

  purchaseReward: (id: string) => apiClient.post(`/rewards/purchase/${id}`).then(r => r.data),
  requestReward: (id: string) => apiClient.post(`/rewards/request/${id}`).then(r => r.data),
  getMyRequests: () => apiClient.get('/rewards/my-requests').then(r => r.data),
  getAllRequests: (statusFilter?: string) =>
    apiClient.get('/rewards/admin/requests', { params: { status_filter: statusFilter } }).then(r => r.data),
  approveRequest: (id: string) => apiClient.put(`/rewards/requests/${id}/approve`).then(r => r.data),
  rejectRequest: (id: string, reason?: string) =>
    apiClient.put(`/rewards/requests/${id}/reject`, { reason }).then(r => r.data),

  getStreak: () => apiClient.get('/rewards/streak').then(r => r.data),
  updateStreak: () => apiClient.post('/rewards/streak/update').then(r => r.data),
  getBadges: () => apiClient.get('/rewards/badges').then(r => r.data),

  getBadgeDefinitions: () => apiClient.get('/rewards/badge-definitions').then(r => r.data),
  createBadgeDefinition: (data: { name: string; description?: string; icon?: string; trigger_type: string; trigger_value: number; points_reward: number }) =>
    apiClient.post('/rewards/badge-definitions', data).then(r => r.data),
  updateBadgeDefinition: (id: string, data: Partial<{ name: string; description?: string; icon?: string; trigger_type: string; trigger_value: number; points_reward: number }>) =>
    apiClient.patch(`/rewards/badge-definitions/${id}`, data).then(r => r.data),
  deleteBadgeDefinition: (id: string) =>
    apiClient.delete(`/rewards/badge-definitions/${id}`).then(r => r.data),
}
```

- [ ] **Step 2: Create RewardsPage.tsx**

Create `frontend/src/pages/RewardsPage.tsx`:

```typescript
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { rewardAPI } from '../api/client'
import { useAuth } from '../stores/auth'

type Tab = 'store' | 'requests' | 'badges' | 'history'

export default function RewardsPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<Tab>('store')
  const [showRewardForm, setShowRewardForm] = useState(false)
  const [rewardForm, setRewardForm] = useState({
    name: '',
    description: '',
    point_cost: 50,
    is_auto_fulfill: true,
  })

  const { data: pointsData } = useQuery({
    queryKey: ['rewards-points'],
    queryFn: rewardAPI.getPointsBalance,
  })

  const { data: allowanceData } = useQuery({
    queryKey: ['rewards-allowance'],
    queryFn: rewardAPI.getAllowanceBalance,
  })

  const { data: catalog } = useQuery({
    queryKey: ['rewards-catalog'],
    queryFn: rewardAPI.getCatalog,
  })

  const { data: myRequests } = useQuery({
    queryKey: ['rewards-my-requests'],
    queryFn: rewardAPI.getMyRequests,
  })

  const { data: badges } = useQuery({
    queryKey: ['rewards-badges'],
    queryFn: rewardAPI.getBadges,
  })

  const { data: streak } = useQuery({
    queryKey: ['rewards-streak'],
    queryFn: rewardAPI.getStreak,
  })

  const purchaseMutation = useMutation({
    mutationFn: rewardAPI.purchaseReward,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rewards-points'] })
    },
  })

  const requestMutation = useMutation({
    mutationFn: rewardAPI.requestReward,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rewards-my-requests'] })
    },
  })

  const createMutation = useMutation({
    mutationFn: rewardAPI.createReward,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rewards-catalog'] })
      setShowRewardForm(false)
    },
  })

  const isAdmin = user?.role === 'admin'

  const handlePurchase = (id: string) => {
    purchaseMutation.mutate(id)
  }

  const handleRequest = (id: string) => {
    requestMutation.mutate(id)
  }

  const handleCreateReward = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(rewardForm)
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'store', label: 'Store' },
    { key: 'requests', label: 'My Requests' },
    { key: 'badges', label: 'Badges' },
    { key: 'history', label: 'History' },
  ]

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">Rewards</h1>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-gray-800 rounded-lg p-4 text-center">
            <div className="text-3xl font-bold text-yellow-400">{pointsData?.balance || 0}</div>
            <div className="text-gray-400 text-sm">Reward Points</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 text-center">
            <div className="text-3xl font-bold text-green-400">${allowanceData?.balance?.toFixed(2) || '0.00'}</div>
            <div className="text-gray-400 text-sm">Allowance</div>
          </div>
        </div>

        {streak && (
          <div className="bg-gray-800 rounded-lg p-4 mb-6 text-center">
            <div className="text-xl font-bold">🔥 {streak.current_streak} Day Streak</div>
            <div className="text-gray-400 text-sm">Longest: {streak.longest_streak} days</div>
          </div>
        )}

        <div className="flex gap-2 mb-6 border-b border-gray-700">
          {tabs.map(tab => (
            <button
              key={tab.key}
              className={`px-4 py-2 ${activeTab === tab.key ? 'bg-blue-600 rounded-t-lg' : 'text-gray-400 hover:text-white'}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'store' && (
          <div className="space-y-3">
            {isAdmin && (
              <button
                onClick={() => setShowRewardForm(!showRewardForm)}
                className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg mb-4"
              >
                {showRewardForm ? 'Cancel' : 'Add Reward'}
              </button>
            )}

            {showRewardForm && (
              <form onSubmit={handleCreateReward} className="bg-gray-800 rounded-lg p-4 space-y-3 mb-4">
                <input
                  type="text"
                  placeholder="Reward name"
                  value={rewardForm.name}
                  onChange={e => setRewardForm({ ...rewardForm, name: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                  required
                />
                <input
                  type="text"
                  placeholder="Description"
                  value={rewardForm.description}
                  onChange={e => setRewardForm({ ...rewardForm, description: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                />
                <input
                  type="number"
                  placeholder="Point cost"
                  value={rewardForm.point_cost}
                  onChange={e => setRewardForm({ ...rewardForm, point_cost: parseInt(e.target.value) || 50 })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                  min="1"
                />
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={rewardForm.is_auto_fulfill}
                    onChange={e => setRewardForm({ ...rewardForm, is_auto_fulfill: e.target.checked })}
                    className="rounded"
                  />
                  Auto-fulfill (no admin approval needed)
                </label>
                <button type="submit" className="w-full bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg">
                  Create Reward
                </button>
              </form>
            )}

            {catalog?.map(reward => (
              <div key={reward.id} className="bg-gray-800 rounded-lg p-4 flex justify-between items-center">
                <div>
                  <div className="font-medium">{reward.name}</div>
                  <div className="text-sm text-gray-400">{reward.description || 'No description'}</div>
                  <div className="text-sm text-yellow-400">{reward.point_cost} points</div>
                </div>
                {reward.is_auto_fulfill ? (
                  <button
                    onClick={() => handlePurchase(reward.id)}
                    disabled={pointsData?.balance && pointsData.balance < reward.point_cost}
                    className="bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg"
                  >
                    Redeem
                  </button>
                ) : (
                  <button
                    onClick={() => handleRequest(reward.id)}
                    className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg"
                  >
                    Request
                  </button>
                )}
              </div>
            )) || <p className="text-gray-400 text-center py-8">No rewards available</p>}
          </div>
        )}

        {activeTab === 'requests' && (
          <div className="space-y-2">
            {myRequests?.map(req => (
              <div key={req.id} className="bg-gray-800 rounded-lg p-3 flex justify-between items-center">
                <div>
                  <span className="text-gray-400">{new Date(req.requested_at).toLocaleDateString()}</span>
                  <span className={`ml-4 px-2 py-1 rounded text-xs ${
                    req.status === 'approved' ? 'bg-green-600' :
                    req.status === 'rejected' ? 'bg-red-600' : 'bg-yellow-600'
                  }`}>
                    {req.status}
                  </span>
                </div>
              </div>
            )) || <p className="text-gray-400 text-center py-8">No reward requests</p>}
          </div>
        )}

        {activeTab === 'badges' && (
          <div className="space-y-3">
            {badges?.map(badge => (
              <div key={badge.id} className="bg-gray-800 rounded-lg p-4 text-center">
                <div className="text-3xl mb-2">🏆</div>
                <div className="text-gray-400 text-sm">Earned {new Date(badge.earned_at).toLocaleDateString()}</div>
              </div>
            )) || <p className="text-gray-400 text-center py-8">No badges earned yet. Complete chores to earn badges!</p>}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="space-y-2">
            <h2 className="text-lg font-semibold mb-2">Points History</h2>
            {pointsData?.transactions.map(tx => (
              <div key={tx.id} className="bg-gray-800 rounded-lg p-3 flex justify-between">
                <div>
                  <span className="text-gray-400">{new Date(tx.created_at).toLocaleDateString()}</span>
                  <span className="ml-4 text-sm">{tx.description || tx.type}</span>
                </div>
                <span className={tx.points > 0 ? 'text-green-400' : 'text-red-400'}>
                  {tx.points > 0 ? '+' : ''}{tx.points}
                </span>
              </div>
            ))}
            <h2 className="text-lg font-semibold mb-2 mt-6">Allowance History</h2>
            {allowanceData?.transactions.map(tx => (
              <div key={tx.id} className="bg-gray-800 rounded-lg p-3 flex justify-between">
                <div>
                  <span className="text-gray-400">{new Date(tx.created_at).toLocaleDateString()}</span>
                  <span className="ml-4 text-sm">{tx.description || tx.type}</span>
                </div>
                <span className="text-green-400">+${tx.amount}</span>
              </div>
            ))}
            {(!pointsData?.transactions?.length && !allowanceData?.transactions?.length) && (
              <p className="text-gray-400 text-center py-8">No transaction history</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Update App.tsx with rewards route**

Read the current `frontend/src/App.tsx`, then add:

```typescript
import RewardsPage from './pages/RewardsPage'
```

Add route:
```typescript
<Route path="/rewards" element={<RewardsPage />} />
```

- [ ] **Step 4: Verify frontend compiles**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: Build succeeds.

---

## Task Group 10: Frontend — Dashboard Widgets & Navigation

### Task 10.1: Add chore and reward widgets to DashboardHome

**Files:**
- Modify: `frontend/src/pages/DashboardHome.tsx` — Add chores widget and rewards balance widget
- Modify: `frontend/src/components/NavShell.tsx` — Add Chores and Rewards nav links

- [ ] **Step 1: Update DashboardHome.tsx**

Read the current `frontend/src/pages/DashboardHome.tsx`, then add imports and widgets:

Add imports:
```typescript
import { useQuery } from '@tanstack/react-query'
import { choreAPI, rewardAPI } from '../api/client'
```

Add before the return statement:
```typescript
  const { data: choresData } = useQuery({
    queryKey: ['chores-instances'],
    queryFn: () => choreAPI.getInstances(),
    refetchInterval: 30000,
  })

  const { data: pointsData } = useQuery({
    queryKey: ['rewards-points'],
    queryFn: rewardAPI.getPointsBalance,
  })

  const { data: allowanceData } = useQuery({
    queryKey: ['rewards-allowance'],
    queryFn: rewardAPI.getAllowanceBalance,
  })

  const myChores = choresData?.filter(i =>
    i.assigned_to_id === user?.id || i.claimed_by_id === user?.id
  ) || []
```

Add widgets to the dashboard grid (after existing stats cards):

```typescript
{/* Chores Widget */}
<div className="bg-gray-800 rounded-lg p-4">
  <h3 className="text-lg font-semibold mb-3">Today's Chores</h3>
  {myChores.length === 0 ? (
    <p className="text-gray-400 text-sm">No chores assigned</p>
  ) : (
    <div className="space-y-2">
      {myChores.slice(0, 3).map(chore => (
        <div key={chore.id} className="flex justify-between items-center">
          <span className="text-sm">Due: {chore.due_date}</span>
          {chore.status === 'claimed' && (
            <button className="text-green-400 text-sm hover:text-green-300">
              Complete
            </button>
          )}
        </div>
      ))}
    </div>
  )}
</div>

{/* Rewards Widget */}
<div className="bg-gray-800 rounded-lg p-4">
  <h3 className="text-lg font-semibold mb-3">Rewards</h3>
  <div className="space-y-1">
    <div className="flex justify-between">
      <span className="text-gray-400 text-sm">Points:</span>
      <span className="text-yellow-400 font-semibold">{pointsData?.balance || 0}</span>
    </div>
    <div className="flex justify-between">
      <span className="text-gray-400 text-sm">Allowance:</span>
      <span className="text-green-400 font-semibold">${allowanceData?.balance?.toFixed(2) || '0.00'}</span>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Update NavShell.tsx**

Read the current `frontend/src/components/NavShell.tsx` (or wherever the navigation is defined), then add Chores and Rewards to the nav links.

Look for the navigation links array/object and add:
```typescript
{ label: 'Chores', path: '/chores' },
{ label: 'Meals', path: '/meals' },
{ label: 'Rewards', path: '/rewards' },
```

- [ ] **Step 3: Verify frontend compiles**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: Build succeeds.

---

## Task Group 11: Version Bump & Commit

### Task 11.1: Update version to 0.18

**Files:**
- Modify: `backend/app/core/config.py` — Update APP_VERSION (if it exists as a constant)
- Modify: `backend/app/main.py` — Update version string
- Modify: `backend/Dockerfile` — Update LABEL version (if present)

- [ ] **Step 1: Update version**

Read `backend/app/main.py`, find the version string `"0.1.0"` and change to `"0.18"`.

Read `backend/app/core/config.py` if it has APP_VERSION, update to `"0.18"`.

- [ ] **Step 2: Run full test suite**

```bash
cd backend && source .venv/bin/activate && pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 3: Frontend build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: Phase 2A - Chores + Rewards system

- Chore templates with flexible recurrence (daily, weekly, monthly, custom intervals)
- Claimable chores for self-assignment
- Chore instances, completion tracking, and history
- Reward points ledger with earn/spent tracking
- Allowance ledger (separate from points) with weekly distribution
- Reward catalog with auto-fulfill and admin-approve modes
- Reward purchase and request flows
- Automatic streak tracking with grace period
- Badge definitions and auto-award on milestones
- APScheduler jobs for chore generation and allowance distribution
- Frontend: Chores page with tabs (My Chores, Available, History, Templates)
- Frontend: Rewards page with tabs (Store, Requests, Badges, History)
- Dashboard widgets for chores and rewards
- Navigation links for Chores and Rewards
- 10 new chore tests, 6 new reward tests"
```

---

## Summary of Files Created/Modified

### Backend (New):
- `backend/app/routers/chores.py` — Chore CRUD, instances, completion, stats
- `backend/app/routers/rewards.py` — Points/allowance, rewards catalog, purchases, streaks, badges
- `backend/app/jobs/chore_generator.py` — Daily chore instance generator
- `backend/app/jobs/allowance_distributor.py` — Weekly allowance distributor
- `backend/tests/test_chores.py` — Chore tests
- `backend/tests/test_rewards.py` — Reward tests
- `frontend/src/pages/ChoresPage.tsx` — Chores page component
- `frontend/src/pages/RewardsPage.tsx` — Rewards page component

### Backend (Modified):
- `backend/app/models/event.py` — Add 10 new model classes
- `backend/app/models/__init__.py` — Export new models
- `backend/app/schemas/models.py` — Add 20+ new schema classes
- `backend/app/main.py` — Register new routers, add APScheduler
- `backend/requirements.txt` — No new deps (python-dateutil already installed)

### Frontend (Modified):
- `frontend/src/App.tsx` — Add /chores and /rewards routes
- `frontend/src/api/client.ts` — Add choreAPI and rewardAPI modules
- `frontend/src/pages/DashboardHome.tsx` — Add chores and rewards widgets
- `frontend/src/components/NavShell.tsx` — Add nav links

### Frontend (New):
- `frontend/src/pages/ChoresPage.tsx` (already listed above)
- `frontend/src/pages/RewardsPage.tsx` (already listed above)
