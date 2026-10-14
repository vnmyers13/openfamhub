"""Chores: templates (admin), today's instances, claim/complete/undo, points.

Rules ported from v0.29, with its bugs fixed:
- Only the assignee or an admin can claim or complete an assigned chore;
  anyone (not viewers) can claim an open one.
- Completing credits the points ledger in the same transaction, exactly once
  (a conditional status update plus a unique ledger source); undo writes a
  reversal entry. Points go to the assignee, else whoever claimed it.
- Dates are the family's local dates.
"""
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import queue_event
from app.core.security import get_current_user, require_role
from app.models.chores import ChoreCompletion, ChoreInstance, ChoreTemplate, PointsEntry
from app.models.family import Family
from app.models.user import User
from app.schemas.chores import (
    ByUserRow, ChoreCreate, ChoreInstanceResponse, ChoreStats, ChoreTemplateResponse, ChoreUpdate,
    CompletionLogEntry, PointsRow,
)
from app.services.chores import OPEN, family_today, reschedule_template, retire_template, generate_instances
from app.services import rewards as rewards_svc

router = APIRouter()

MAX_RANGE_DAYS = 62


# ---- helpers ---------------------------------------------------------------

async def family_zone(db: AsyncSession, family_id: str) -> str:
    family = await db.get(Family, family_id)
    return family.timezone if family else "UTC"


async def today_for(db: AsyncSession, family_id: str) -> date:
    return family_today(await family_zone(db, family_id))


async def family_members(db: AsyncSession, family_id: str) -> dict[str, User]:
    result = await db.execute(select(User).where(User.family_id == family_id, User.is_deleted == False))  # noqa: E712
    return {u.id: u for u in result.scalars().all()}


async def check_member(db: AsyncSession, family_id: str, user_id: Optional[str]) -> None:
    if user_id is not None and user_id not in await family_members(db, family_id):
        raise HTTPException(status_code=400, detail="That person isn't in this family")


def deny_viewers(user: User) -> None:
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers can't change chores")


def to_instance(inst: ChoreInstance, template: ChoreTemplate) -> ChoreInstanceResponse:
    return ChoreInstanceResponse(
        id=inst.id, template_id=inst.template_id, title=template.title, points=template.points,
        due_date=inst.due_date, status=inst.status, assigned_to=inst.assigned_to,
        claimed_by=inst.claimed_by, claimed_at=inst.claimed_at, completed_by=inst.completed_by,
        completed_at=inst.completed_at, routine_id=template.routine_id,
    )


async def load_instance(db: AsyncSession, user: User, instance_id: str) -> tuple[ChoreInstance, ChoreTemplate]:
    inst = await db.get(ChoreInstance, instance_id)
    template = await db.get(ChoreTemplate, inst.template_id) if inst is not None else None
    if inst is None or template is None or inst.family_id != user.family_id:
        raise HTTPException(status_code=404, detail="Chore not found")
    return inst, template


def credit_target(inst: ChoreInstance, actor: User) -> str:
    return inst.assigned_to or inst.claimed_by or actor.id


# ---- templates -------------------------------------------------------------

@router.get("/templates", response_model=List[ChoreTemplateResponse])
async def list_templates(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(ChoreTemplate)
        .where(ChoreTemplate.family_id == user.family_id, ChoreTemplate.is_active == True,  # noqa: E712
               ChoreTemplate.routine_id.is_(None))
        .order_by(func.lower(ChoreTemplate.title))
    )
    return list(result.scalars().all())


@router.post("/templates", response_model=ChoreTemplateResponse, status_code=201)
async def create_template(data: ChoreCreate, db: AsyncSession = Depends(get_db),
                          admin: User = Depends(require_role("admin"))):
    await check_member(db, admin.family_id, data.assigned_to)
    today = await today_for(db, admin.family_id)
    template = ChoreTemplate(
        family_id=admin.family_id, title=data.title, description=data.description, points=data.points,
        assignment=data.assignment, assigned_to=data.assigned_to,
        repeat=data.repeat.model_dump(exclude_none=True) if data.repeat else None,
        start_date=data.start_date or today, created_by=admin.id,
    )
    db.add(template)
    await db.flush()
    await generate_instances(db, admin.family_id, today, template_ids=[template.id])
    await db.refresh(template)
    queue_event(db, "chores_updated", {})
    return template


@router.patch("/templates/{template_id}", response_model=ChoreTemplateResponse)
async def update_template(template_id: str, data: ChoreUpdate, db: AsyncSession = Depends(get_db),
                          admin: User = Depends(require_role("admin"))):
    template = await db.get(ChoreTemplate, template_id)
    if template is None or template.family_id != admin.family_id or template.routine_id is not None:
        raise HTTPException(status_code=404, detail="Chore not found")
    fields = data.model_dump(exclude_unset=True)
    if "repeat" in fields:
        fields["repeat"] = data.repeat.model_dump(exclude_none=True) if data.repeat else None
    for key, value in fields.items():
        setattr(template, key, value)
    if template.assignment == "claimable":
        template.assigned_to = None
    elif not template.assigned_to:
        raise HTTPException(status_code=400, detail="An assigned chore needs someone to do it")
    await check_member(db, admin.family_id, template.assigned_to)
    await db.flush()
    await reschedule_template(db, template, await today_for(db, admin.family_id))
    await db.refresh(template)
    queue_event(db, "chores_updated", {})
    return template


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str, db: AsyncSession = Depends(get_db),
                          admin: User = Depends(require_role("admin"))):
    template = await db.get(ChoreTemplate, template_id)
    if template is None or template.family_id != admin.family_id or template.routine_id is not None:
        raise HTTPException(status_code=404, detail="Chore not found")
    await retire_template(db, template, await today_for(db, admin.family_id))
    queue_event(db, "chores_updated", {})
    return {"ok": True}


# ---- instances -------------------------------------------------------------

@router.get("/instances", response_model=List[ChoreInstanceResponse])
async def list_instances(
    start: Optional[date] = None, end: Optional[date] = None,
    scope: str = Query("family", pattern="^(family|mine|available)$"),
    include_routines: bool = False,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    today = await today_for(db, user.family_id)
    start = start or today
    end = end or start
    if end < start or (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Choose a range of up to {MAX_RANGE_DAYS} days, start before end")
    query = (
        select(ChoreInstance, ChoreTemplate)
        .join(ChoreTemplate, ChoreTemplate.id == ChoreInstance.template_id)
        .where(ChoreInstance.family_id == user.family_id, ChoreInstance.due_date >= start, ChoreInstance.due_date <= end)
    )
    if not include_routines:
        query = query.where(ChoreTemplate.routine_id.is_(None))
    if scope == "mine":
        query = query.where(or_(ChoreInstance.assigned_to == user.id, ChoreInstance.claimed_by == user.id))
    elif scope == "available":
        query = query.where(ChoreTemplate.assignment == "claimable", ChoreInstance.status == "pending",
                            ChoreInstance.claimed_by.is_(None))
    result = await db.execute(query.order_by(ChoreInstance.due_date, func.lower(ChoreTemplate.title)))
    return [to_instance(i, t) for i, t in result.all()]


@router.post("/instances/{instance_id}/claim", response_model=ChoreInstanceResponse)
async def claim(instance_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    deny_viewers(user)
    inst, template = await load_instance(db, user, instance_id)
    if inst.assigned_to and inst.assigned_to != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="This chore is assigned to someone else")
    if inst.claimed_by == user.id and inst.status == "claimed":
        return to_instance(inst, template)
    if inst.status != "pending" or (inst.claimed_by and inst.claimed_by != user.id):
        raise HTTPException(status_code=409, detail="Someone else has this chore, or it's already done")
    inst.status, inst.claimed_by, inst.claimed_at = "claimed", user.id, datetime.now(timezone.utc)
    await db.flush()
    queue_event(db, "chores_updated", {})
    return to_instance(inst, template)


@router.post("/instances/{instance_id}/unclaim", response_model=ChoreInstanceResponse)
async def unclaim(instance_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    deny_viewers(user)
    inst, template = await load_instance(db, user, instance_id)
    if inst.claimed_by != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only whoever claimed it (or an admin) can give it back")
    if inst.status != "claimed":
        raise HTTPException(status_code=409, detail="This chore isn't claimed")
    inst.status, inst.claimed_by, inst.claimed_at = "pending", None, None
    await db.flush()
    queue_event(db, "chores_updated", {})
    return to_instance(inst, template)


@router.post("/instances/{instance_id}/complete", response_model=ChoreInstanceResponse)
async def complete(instance_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    deny_viewers(user)
    return await complete_instance_for_user(db, user, instance_id)


async def complete_instance_for_user(db: AsyncSession, user: User, instance_id: str) -> ChoreInstanceResponse:
    inst, template = await load_instance(db, user, instance_id)
    allowed = (
        user.role == "admin" or inst.assigned_to == user.id or inst.claimed_by == user.id
        or (not inst.assigned_to and not inst.claimed_by)
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="This chore belongs to someone else")
    if inst.status not in OPEN:
        raise HTTPException(status_code=409, detail="This chore is already done or was missed")

    now = datetime.now(timezone.utc)
    claimed_by = inst.claimed_by or (None if inst.assigned_to else user.id)
    # Conditional update: only one request can move it out of an open state.
    result = await db.execute(
        update(ChoreInstance)
        .where(ChoreInstance.id == inst.id, ChoreInstance.status.in_(OPEN))
        .values(status="completed", completed_by=user.id, completed_at=now, claimed_by=claimed_by,
                claimed_at=inst.claimed_at or (now if claimed_by and not inst.claimed_by else None))
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=409, detail="This chore is already done or was missed")
    await db.refresh(inst)

    credited = credit_target(inst, user)
    completion = ChoreCompletion(family_id=user.family_id, instance_id=inst.id, completed_by=user.id,
                                 credited_to=credited, points=template.points, completed_at=now)
    db.add(completion)
    await db.flush()
    if template.points:
        db.add(PointsEntry(family_id=user.family_id, user_id=credited, delta=template.points,
                           reason=f"Chore: {template.title}", source_type="chore", source_id=completion.id))
        await db.flush()
    # Badges are checked in the same transaction, so a badge and its bonus land with the chore.
    if await rewards_svc.award_badges(db, user.family_id, credited):
        queue_event(db, "rewards_updated", {})
    queue_event(db, "chores_updated", {})
    return to_instance(inst, template)


@router.post("/instances/{instance_id}/undo", response_model=ChoreInstanceResponse)
async def undo(instance_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    deny_viewers(user)
    inst, template = await load_instance(db, user, instance_id)
    completion = (await db.execute(
        select(ChoreCompletion)
        .where(ChoreCompletion.instance_id == inst.id, ChoreCompletion.undone_at.is_(None))
        .order_by(ChoreCompletion.completed_at.desc())
    )).scalars().first()
    if inst.status != "completed" or completion is None:
        raise HTTPException(status_code=409, detail="This chore isn't done")
    if user.role != "admin" and user.id not in (completion.completed_by, completion.credited_to):
        raise HTTPException(status_code=403, detail="Only whoever did it (or an admin) can undo it")

    now = datetime.now(timezone.utc)
    completion.undone_at, completion.undone_by = now, user.id
    today = await today_for(db, user.family_id)
    inst.status = "missed" if inst.due_date < today else ("claimed" if inst.claimed_by else "pending")
    inst.completed_by = inst.completed_at = None
    if completion.points:
        db.add(PointsEntry(family_id=user.family_id, user_id=completion.credited_to, delta=-completion.points,
                           reason=f"Undone: {template.title}", source_type="chore_undo", source_id=completion.id))
    await db.flush()
    queue_event(db, "chores_updated", {})
    return to_instance(inst, template)


# ---- views -----------------------------------------------------------------

@router.get("/by-user", response_model=List[ByUserRow])
async def by_user(start: Optional[date] = None, end: Optional[date] = None,
                  db: AsyncSession = Depends(get_db), admin: User = Depends(require_role("admin"))):
    today = await today_for(db, admin.family_id)
    start, end = start or today, end or start or today
    owner = func.coalesce(ChoreInstance.assigned_to, ChoreInstance.claimed_by)
    rows = (await db.execute(
        select(owner, ChoreInstance.status, func.count())
        .join(ChoreTemplate, ChoreTemplate.id == ChoreInstance.template_id)
        .where(ChoreInstance.family_id == admin.family_id, ChoreInstance.due_date >= start,
               ChoreInstance.due_date <= end, ChoreTemplate.routine_id.is_(None))
        .group_by(owner, ChoreInstance.status)
    )).all()
    members = await family_members(db, admin.family_id)
    counts: dict[Optional[str], dict[str, int]] = {}
    for user_id, status, n in rows:
        bucket = counts.setdefault(user_id, {"pending": 0, "completed": 0, "missed": 0})
        key = "pending" if status in OPEN else status  # claimed counts as pending
        if key in bucket:
            bucket[key] += n
    out = [
        ByUserRow(user_id=uid, display_name=members[uid].display_name if uid in members else "Unassigned", **c)
        for uid, c in counts.items()
    ]
    return sorted(out, key=lambda r: (r.user_id is None, r.display_name.lower()))


async def ledger_balance(db: AsyncSession, family_id: str, user_id: str) -> int:
    return (await db.execute(
        select(func.coalesce(func.sum(PointsEntry.delta), 0))
        .where(PointsEntry.family_id == family_id, PointsEntry.user_id == user_id)
    )).scalar()


@router.get("/stats", response_model=ChoreStats)
async def stats(user_id: Optional[str] = None, db: AsyncSession = Depends(get_db),
                user: User = Depends(get_current_user)):
    target = user_id or user.id
    if target != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="You can only see your own stats")
    tz_name = await family_zone(db, user.family_id)
    zone = rewards_svc.zone_for(tz_name)
    done = (await db.execute(
        select(ChoreCompletion.completed_at)
        .where(ChoreCompletion.family_id == user.family_id, ChoreCompletion.credited_to == target,
               ChoreCompletion.undone_at.is_(None))
    )).scalars().all()
    days = {c.astimezone(zone).date() for c in done}
    today = family_today(tz_name)
    week_start = rewards_svc.week_start(today)
    streak = rewards_svc.streak_from(days, today)
    return ChoreStats(
        user_id=target, completed_total=len(done),
        completed_this_week=sum(1 for c in done if c.astimezone(zone).date() >= week_start),
        points_balance=await ledger_balance(db, user.family_id, target), streak_days=streak,
    )


@router.get("/points", response_model=List[PointsRow])
async def points(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    totals = dict((await db.execute(
        select(PointsEntry.user_id, func.sum(PointsEntry.delta))
        .where(PointsEntry.family_id == user.family_id).group_by(PointsEntry.user_id)
    )).all())
    members = await family_members(db, user.family_id)
    rows = [PointsRow(user_id=u.id, display_name=u.display_name, points=totals.get(u.id, 0) or 0) for u in members.values()]
    return sorted(rows, key=lambda r: r.display_name.lower())


@router.get("/log", response_model=List[CompletionLogEntry])
async def completion_log(limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    query = (
        select(ChoreCompletion, ChoreTemplate.title)
        .join(ChoreInstance, ChoreInstance.id == ChoreCompletion.instance_id)
        .join(ChoreTemplate, ChoreTemplate.id == ChoreInstance.template_id)
        .where(ChoreCompletion.family_id == user.family_id)
    )
    if user.role != "admin":
        query = query.where(or_(ChoreCompletion.completed_by == user.id, ChoreCompletion.credited_to == user.id))
    result = await db.execute(query.order_by(ChoreCompletion.completed_at.desc()).limit(limit))
    return [
        CompletionLogEntry(id=c.id, instance_id=c.instance_id, title=title, completed_by=c.completed_by,
                           credited_to=c.credited_to, points=c.points, completed_at=c.completed_at, undone_at=c.undone_at)
        for c, title in result.all()
    ]
