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
    result = db.execute(select(UserStreak).where(UserStreak.user_id == user_id))
    streak = result.scalar_one_or_none()

    if streak is None:
        streak = UserStreak(
            user_id=user_id,
            current_streak=0,
            longest_streak=0,
            grace_days=1,
        )
        db.add(streak)
        db.flush()
        db.refresh(streak)

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
        reference_id=request_entry.reward_id,
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
    req: Optional[dict] = None,
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

    streak = await _get_or_create_streak(db, user_id)

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
