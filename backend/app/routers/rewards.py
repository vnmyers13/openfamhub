"""Rewards: the catalog, redemptions, points adjustments, badges, allowance and
family progress (Phase 6).

Ported from v0.29 with its gaps closed:
- Every query is scoped to the caller's family.
- Spending writes to the append-only points ledger. A redemption takes its
  points when it's made, so a pending request can't be spent twice, and a
  rejection or cancellation refunds them. Each move is a ledger row keyed by
  the redemption, and a status can only leave "pending" once (conditional
  update), so approve/reject can't double-charge or double-refund.
- Allowance is whole cents in its own ledger, never strings.
"""
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import queue_event
from app.core.security import get_current_user, require_role
from app.models.chores import PointsEntry
from app.models.rewards import AllowanceEntry, AllowancePlan, BadgeDefinition, Redemption, Reward
from app.models.user import User
from app.schemas.rewards import (
    AllowanceAdjust, AllowanceEntryResponse, AllowanceRow, AllowanceSet, BadgeCreate, BadgeResponse, BadgeUpdate,
    DecisionRequest, LedgerEntry, PointsAdjust, ProgressRow, RedemptionResponse, RewardCreate, RewardResponse,
    RewardUpdate,
)
from app.services import rewards as svc

router = APIRouter()
admin_only = require_role("admin")


# ---- helpers ---------------------------------------------------------------

async def member_or_400(db: AsyncSession, family_id: str, user_id: str) -> User:
    user = await db.get(User, user_id)
    if user is None or user.family_id != family_id or user.is_deleted:
        raise HTTPException(status_code=400, detail="That person isn't in this family")
    return user


def own_or_admin(user: User, target: Optional[str]) -> str:
    target = target or user.id
    if target != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="You can only see your own")
    return target


def changed(db: AsyncSession) -> None:
    queue_event(db, "rewards_updated", {})


def to_reward(r: Reward) -> RewardResponse:
    return RewardResponse(id=r.id, name=r.name, description=r.description, icon=r.icon, point_cost=r.point_cost,
                          needs_approval=r.needs_approval, is_active=r.is_active)


def to_redemption(r: Redemption) -> RedemptionResponse:
    return RedemptionResponse(id=r.id, reward_id=r.reward_id, user_id=r.user_id, reward_name=r.reward_name,
                              point_cost=r.point_cost, status=r.status, note=r.note, requested_at=r.requested_at,
                              decided_at=r.decided_at, decided_by=r.decided_by)


def to_badge(b: BadgeDefinition) -> BadgeResponse:
    return BadgeResponse(id=b.id, name=b.name, description=b.description, icon=b.icon, kind=b.kind,
                         threshold=b.threshold, bonus_points=b.bonus_points, is_active=b.is_active)


async def load_reward(db: AsyncSession, family_id: str, reward_id: str) -> Reward:
    reward = await db.get(Reward, reward_id)
    if reward is None or reward.family_id != family_id:
        raise HTTPException(status_code=404, detail="Reward not found")
    return reward


async def load_redemption(db: AsyncSession, family_id: str, redemption_id: str) -> Redemption:
    red = await db.get(Redemption, redemption_id)
    if red is None or red.family_id != family_id:
        raise HTTPException(status_code=404, detail="Request not found")
    return red


async def load_badge(db: AsyncSession, family_id: str, badge_id: str) -> BadgeDefinition:
    badge = await db.get(BadgeDefinition, badge_id)
    if badge is None or badge.family_id != family_id:
        raise HTTPException(status_code=404, detail="Badge not found")
    return badge


# ---- catalog -----------------------------------------------------------------

@router.get("/catalog", response_model=List[RewardResponse])
async def list_rewards(include_inactive: bool = False, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    query = select(Reward).where(Reward.family_id == user.family_id)
    if not (include_inactive and user.role == "admin"):
        query = query.where(Reward.is_active == True)  # noqa: E712
    rows = (await db.execute(query.order_by(Reward.point_cost, Reward.name))).scalars().all()
    return [to_reward(r) for r in rows]


@router.post("/catalog", response_model=RewardResponse, status_code=201)
async def create_reward(data: RewardCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(admin_only)):
    reward = Reward(family_id=admin.family_id, name=data.name, description=data.description, icon=data.icon,
                    point_cost=data.point_cost, needs_approval=data.needs_approval, created_by=admin.id)
    db.add(reward)
    await db.flush()
    changed(db)
    return to_reward(reward)


@router.patch("/catalog/{reward_id}", response_model=RewardResponse)
async def update_reward(reward_id: str, data: RewardUpdate, db: AsyncSession = Depends(get_db),
                        admin: User = Depends(admin_only)):
    reward = await load_reward(db, admin.family_id, reward_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is None and key in ("name", "point_cost", "needs_approval", "is_active"):
            continue
        setattr(reward, key, value)
    await db.flush()
    changed(db)
    return to_reward(reward)


@router.delete("/catalog/{reward_id}")
async def retire_reward(reward_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(admin_only)):
    reward = await load_reward(db, admin.family_id, reward_id)
    reward.is_active = False
    await db.flush()
    changed(db)
    return {"message": "Reward retired"}


# ---- redemptions --------------------------------------------------------------

@router.post("/catalog/{reward_id}/redeem", response_model=RedemptionResponse, status_code=201)
async def redeem(reward_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers can't redeem rewards")
    reward = await load_reward(db, user.family_id, reward_id)
    if not reward.is_active:
        raise HTTPException(status_code=404, detail="Reward not found")
    balance = await svc.points_balance(db, user.family_id, user.id)
    if balance < reward.point_cost:
        raise HTTPException(status_code=409, detail=f"Not enough points: you have {balance}, this costs {reward.point_cost}")
    now = datetime.now(timezone.utc)
    red = Redemption(family_id=user.family_id, reward_id=reward.id, user_id=user.id, reward_name=reward.name,
                     point_cost=reward.point_cost, status="pending" if reward.needs_approval else "approved",
                     requested_at=now, decided_at=None if reward.needs_approval else now)
    db.add(red)
    await db.flush()
    spend = PointsEntry(family_id=user.family_id, user_id=user.id, delta=-reward.point_cost,
                        reason=f"Reward: {reward.name}", source_type="reward", source_id=red.id, created_at=now)
    db.add(spend)
    await db.flush()
    # Re-check with the spend written: two redeems at once (two devices) can
    # both pass the first check. The later one takes its spend back out.
    balance = await svc.points_balance(db, user.family_id, user.id)
    if balance < 0:
        await db.delete(spend)
        await db.delete(red)
        await db.flush()
        raise HTTPException(status_code=409,
                            detail=f"Not enough points: you have {balance + reward.point_cost}, this costs {reward.point_cost}")
    changed(db)
    return to_redemption(red)


@router.get("/redemptions", response_model=List[RedemptionResponse])
async def list_redemptions(status: Optional[Literal["pending", "approved", "rejected", "cancelled"]] = None,
                           user_id: Optional[str] = None, limit: int = Query(100, ge=1, le=500),
                           db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(Redemption).where(Redemption.family_id == user.family_id)
    if user.role != "admin":
        query = query.where(Redemption.user_id == user.id)
    elif user_id:
        query = query.where(Redemption.user_id == user_id)
    if status:
        query = query.where(Redemption.status == status)
    rows = (await db.execute(query.order_by(Redemption.requested_at.desc()).limit(limit))).scalars().all()
    return [to_redemption(r) for r in rows]


async def decide(db: AsyncSession, red: Redemption, status: str, actor: User, note: Optional[str], refund: bool):
    now = datetime.now(timezone.utc)
    # Conditional update: only one request can move it out of "pending".
    result = await db.execute(
        update(Redemption)
        .where(Redemption.id == red.id, Redemption.status == "pending")
        .values(status=status, decided_at=now, decided_by=actor.id, note=note)
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=409, detail="This request was already decided")
    await db.refresh(red)
    if refund:
        db.add(PointsEntry(family_id=red.family_id, user_id=red.user_id, delta=red.point_cost,
                           reason=f"Refund: {red.reward_name}", source_type="reward_refund", source_id=red.id,
                           created_at=now))
    await db.flush()
    changed(db)
    return to_redemption(red)


@router.post("/redemptions/{redemption_id}/approve", response_model=RedemptionResponse)
async def approve(redemption_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(admin_only)):
    red = await load_redemption(db, admin.family_id, redemption_id)
    return await decide(db, red, "approved", admin, None, refund=False)


@router.post("/redemptions/{redemption_id}/reject", response_model=RedemptionResponse)
async def reject(redemption_id: str, data: Optional[DecisionRequest] = None, db: AsyncSession = Depends(get_db),
                 admin: User = Depends(admin_only)):
    red = await load_redemption(db, admin.family_id, redemption_id)
    return await decide(db, red, "rejected", admin, data.note if data else None, refund=True)


@router.post("/redemptions/{redemption_id}/cancel", response_model=RedemptionResponse)
async def cancel(redemption_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    red = await load_redemption(db, user.family_id, redemption_id)
    if red.user_id != user.id:
        raise HTTPException(status_code=404, detail="Request not found")
    return await decide(db, red, "cancelled", user, None, refund=True)


# ---- points -------------------------------------------------------------------

@router.post("/points/adjust", response_model=LedgerEntry, status_code=201)
async def adjust_points(data: PointsAdjust, db: AsyncSession = Depends(get_db), admin: User = Depends(admin_only)):
    await member_or_400(db, admin.family_id, data.user_id)
    entry = PointsEntry(family_id=admin.family_id, user_id=data.user_id, delta=data.delta, reason=data.reason,
                        source_type="adjustment", source_id=svc.new_source_id(), created_at=datetime.now(timezone.utc))
    db.add(entry)
    await db.flush()
    changed(db)
    return LedgerEntry(id=entry.id, delta=entry.delta, reason=entry.reason, source_type=entry.source_type,
                       created_at=entry.created_at)


@router.get("/points/history", response_model=List[LedgerEntry])
async def points_history(user_id: Optional[str] = None, limit: int = Query(50, ge=1, le=200),
                         db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    target = own_or_admin(user, user_id)
    rows = (await db.execute(
        select(PointsEntry)
        .where(PointsEntry.family_id == user.family_id, PointsEntry.user_id == target)
        .order_by(PointsEntry.created_at.desc()).limit(limit)
    )).scalars().all()
    return [LedgerEntry(id=e.id, delta=e.delta, reason=e.reason, source_type=e.source_type, created_at=e.created_at)
            for e in rows]


# ---- badges -------------------------------------------------------------------

@router.get("/badges", response_model=List[BadgeResponse])
async def list_badges(include_inactive: bool = False, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    query = select(BadgeDefinition).where(BadgeDefinition.family_id == user.family_id)
    if not (include_inactive and user.role == "admin"):
        query = query.where(BadgeDefinition.is_active == True)  # noqa: E712
    rows = (await db.execute(query.order_by(BadgeDefinition.kind, BadgeDefinition.threshold))).scalars().all()
    return [to_badge(b) for b in rows]


@router.post("/badges", response_model=BadgeResponse, status_code=201)
async def create_badge(data: BadgeCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(admin_only)):
    badge = BadgeDefinition(family_id=admin.family_id, **data.model_dump())
    db.add(badge)
    await db.flush()
    await svc.award_badge_to_all(db, admin.family_id, badge)  # people who already qualify get it now
    changed(db)
    return to_badge(badge)


@router.patch("/badges/{badge_id}", response_model=BadgeResponse)
async def update_badge(badge_id: str, data: BadgeUpdate, db: AsyncSession = Depends(get_db),
                       admin: User = Depends(admin_only)):
    badge = await load_badge(db, admin.family_id, badge_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is None and key not in ("description", "icon"):
            continue
        setattr(badge, key, value)
    await db.flush()
    await svc.award_badge_to_all(db, admin.family_id, badge)
    changed(db)
    return to_badge(badge)


@router.delete("/badges/{badge_id}")
async def retire_badge(badge_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(admin_only)):
    badge = await load_badge(db, admin.family_id, badge_id)
    badge.is_active = False  # earned copies stay
    await db.flush()
    changed(db)
    return {"message": "Badge retired"}


# ---- progress -----------------------------------------------------------------

@router.get("/progress", response_model=List[ProgressRow])
async def family_progress(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return [ProgressRow(**vars(r)) for r in await svc.progress(db, user.family_id)]


# ---- allowance ----------------------------------------------------------------

async def allowance_row(db: AsyncSession, member: User, plan: Optional[AllowancePlan], now_local: datetime) -> AllowanceRow:
    return AllowanceRow(
        user_id=member.id, display_name=member.display_name, weekly_cents=plan.weekly_cents if plan else 0,
        balance_cents=await svc.allowance_balance(db, member.family_id, member.id),
        next_payout=svc.next_payout(plan, now_local),
    )


@router.get("/allowance", response_model=List[AllowanceRow])
async def list_allowance(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    zone = await svc.family_zone(db, user.family_id)
    now_local = datetime.now(zone)
    members = await svc.earners(db, user.family_id) if user.role == "admin" else [user]
    plans = {p.user_id: p for p in (await db.execute(
        select(AllowancePlan).where(AllowancePlan.family_id == user.family_id)
    )).scalars().all()}
    return [await allowance_row(db, m, plans.get(m.id), now_local) for m in members]


@router.put("/allowance/{user_id}", response_model=AllowanceRow)
async def set_allowance(user_id: str, data: AllowanceSet, db: AsyncSession = Depends(get_db),
                        admin: User = Depends(admin_only)):
    member = await member_or_400(db, admin.family_id, user_id)
    zone = await svc.family_zone(db, admin.family_id)
    now_local = datetime.now(zone)
    plan = (await db.execute(select(AllowancePlan).where(AllowancePlan.user_id == user_id))).scalar_one_or_none()
    if plan is None:
        plan = AllowancePlan(family_id=admin.family_id, user_id=user_id, weekly_cents=0,
                             start_week=svc.first_payout_week(now_local))
        db.add(plan)
    elif plan.weekly_cents <= 0 and data.weekly_cents > 0:
        plan.start_week = svc.first_payout_week(now_local)  # restarting: no back pay for the weeks it was off
    plan.weekly_cents = data.weekly_cents
    await db.flush()
    changed(db)
    return await allowance_row(db, member, plan, now_local)


@router.post("/allowance/{user_id}/adjust", response_model=AllowanceEntryResponse, status_code=201)
async def adjust_allowance(user_id: str, data: AllowanceAdjust, db: AsyncSession = Depends(get_db),
                           admin: User = Depends(admin_only)):
    await member_or_400(db, admin.family_id, user_id)
    entry = AllowanceEntry(family_id=admin.family_id, user_id=user_id, delta_cents=data.delta_cents,
                           reason=data.reason, source_type="adjustment", source_id=svc.new_source_id(),
                           created_by=admin.id, created_at=datetime.now(timezone.utc))
    db.add(entry)
    await db.flush()
    changed(db)
    return AllowanceEntryResponse(id=entry.id, delta_cents=entry.delta_cents, reason=entry.reason,
                                  source_type=entry.source_type, week_start=entry.week_start, created_at=entry.created_at)


@router.get("/allowance/{user_id}/history", response_model=List[AllowanceEntryResponse])
async def allowance_history(user_id: str, limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_current_user)):
    target = own_or_admin(user, user_id)
    rows = (await db.execute(
        select(AllowanceEntry)
        .where(AllowanceEntry.family_id == user.family_id, AllowanceEntry.user_id == target)
        .order_by(AllowanceEntry.created_at.desc(), AllowanceEntry.week_start.desc()).limit(limit)
    )).scalars().all()
    return [AllowanceEntryResponse(id=e.id, delta_cents=e.delta_cents, reason=e.reason, source_type=e.source_type,
                                   week_start=e.week_start, created_at=e.created_at) for e in rows]
