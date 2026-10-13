"""Routines: ordered steps (morning, bedtime) built on chore templates.

Each step is a ChoreTemplate with routine_id and position; it repeats with
the routine and is completed like any chore (credits points to the routine's
assignee). Step order is the list order on every save.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import queue_event
from app.core.security import get_current_user, require_role
from app.models.chores import ChoreInstance, ChoreTemplate, Routine
from app.models.user import User
from app.routers.chores import check_member, family_members, today_for
from app.schemas.chores import (
    RoutineCreate, RoutineResponse, RoutineRun, RoutineRunStep, RoutineStep, RoutineUpdate,
)
from app.services.chores import reschedule_template, retire_template

router = APIRouter()


async def active_steps(db: AsyncSession, routine_id: str) -> list[ChoreTemplate]:
    result = await db.execute(
        select(ChoreTemplate).where(ChoreTemplate.routine_id == routine_id, ChoreTemplate.is_active == True)  # noqa: E712
        .order_by(ChoreTemplate.position)
    )
    return list(result.scalars().all())


async def to_response(db: AsyncSession, r: Routine) -> RoutineResponse:
    steps = await active_steps(db, r.id)
    return RoutineResponse(
        id=r.id, name=r.name, assigned_to=r.assigned_to, start_time=r.start_time, repeat=r.repeat,
        start_date=r.start_date,
        steps=[RoutineStep(id=s.id, title=s.title, minutes=s.minutes or 1, points=s.points) for s in steps],
    )


def apply_schedule(step: ChoreTemplate, r: Routine) -> None:
    """Steps follow their routine's schedule and assignee."""
    step.assigned_to = r.assigned_to
    step.assignment = "assigned" if r.assigned_to else "claimable"
    step.repeat = r.repeat
    step.start_date = r.start_date


async def load(db: AsyncSession, user: User, routine_id: str) -> Routine:
    r = await db.get(Routine, routine_id)
    if r is None or r.family_id != user.family_id or not r.is_active:
        raise HTTPException(status_code=404, detail="Routine not found")
    return r


@router.get("", response_model=List[RoutineResponse])
async def list_routines(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Routine).where(Routine.family_id == user.family_id, Routine.is_active == True)  # noqa: E712
        .order_by(Routine.start_time, Routine.name)
    )
    return [await to_response(db, r) for r in result.scalars().all()]


@router.post("", response_model=RoutineResponse, status_code=201)
async def create_routine(data: RoutineCreate, db: AsyncSession = Depends(get_db),
                         admin: User = Depends(require_role("admin"))):
    await check_member(db, admin.family_id, data.assigned_to)
    today = await today_for(db, admin.family_id)
    r = Routine(family_id=admin.family_id, name=data.name.strip(), assigned_to=data.assigned_to,
                start_time=data.start_time, start_date=data.start_date or today, created_by=admin.id,
                repeat=data.repeat.model_dump(exclude_none=True) if data.repeat else {"every": "day"})
    db.add(r)
    await db.flush()
    for position, step in enumerate(data.steps):
        template = ChoreTemplate(family_id=admin.family_id, title=step.title.strip(), points=step.points,
                                 minutes=step.minutes, routine_id=r.id, position=position, created_by=admin.id,
                                 start_date=r.start_date)
        apply_schedule(template, r)
        db.add(template)
        await db.flush()
        await reschedule_template(db, template, today)
    queue_event(db, "chores_updated", {})
    return await to_response(db, r)


@router.patch("/{routine_id}", response_model=RoutineResponse)
async def update_routine(routine_id: str, data: RoutineUpdate, db: AsyncSession = Depends(get_db),
                         admin: User = Depends(require_role("admin"))):
    r = await load(db, admin, routine_id)
    fields = data.model_dump(exclude_unset=True)
    steps_in = fields.pop("steps", None)
    if "assigned_to" in fields:
        await check_member(db, admin.family_id, fields["assigned_to"])
    if "repeat" in fields:
        fields["repeat"] = data.repeat.model_dump(exclude_none=True) if data.repeat else {"every": "day"}
    for key, value in fields.items():
        setattr(r, key, value.strip() if key == "name" else value)
    today = await today_for(db, admin.family_id)

    current = {s.id: s for s in await active_steps(db, r.id)}
    if steps_in is not None:
        kept: list[ChoreTemplate] = []
        for position, step in enumerate(data.steps):
            if step.id:
                template = current.get(step.id)
                if template is None:
                    raise HTTPException(status_code=400, detail="A step doesn't belong to this routine")
            else:
                template = ChoreTemplate(family_id=admin.family_id, routine_id=r.id, created_by=admin.id,
                                         start_date=r.start_date)
                db.add(template)
            template.title, template.minutes, template.points = step.title.strip(), step.minutes, step.points
            template.position = position
            kept.append(template)
        for step_id, template in current.items():
            if step_id not in {t.id for t in kept}:
                await retire_template(db, template, today)
        await db.flush()
    else:
        kept = list(current.values())

    if steps_in is not None or {"assigned_to", "repeat", "start_date"} & fields.keys():
        for template in kept:
            apply_schedule(template, r)
            await db.flush()
            await reschedule_template(db, template, today)
    await db.flush()
    queue_event(db, "chores_updated", {})
    return await to_response(db, r)


@router.delete("/{routine_id}")
async def delete_routine(routine_id: str, db: AsyncSession = Depends(get_db),
                         admin: User = Depends(require_role("admin"))):
    r = await load(db, admin, routine_id)
    today = await today_for(db, admin.family_id)
    for template in await active_steps(db, r.id):
        await retire_template(db, template, today)
    r.is_active = False
    await db.flush()
    queue_event(db, "chores_updated", {})
    return {"ok": True}


async def todays_runs(db: AsyncSession, family_id: str) -> list[RoutineRun]:
    """Active routines with step instances due today (family date), steps in order."""
    today = await today_for(db, family_id)
    rows = (await db.execute(
        select(Routine, ChoreTemplate, ChoreInstance)
        .join(ChoreTemplate, ChoreTemplate.routine_id == Routine.id)
        .join(ChoreInstance, ChoreInstance.template_id == ChoreTemplate.id)
        .where(Routine.family_id == family_id, Routine.is_active == True, ChoreTemplate.is_active == True,  # noqa: E712
               ChoreInstance.due_date == today)
        .order_by(Routine.start_time, Routine.name, ChoreTemplate.position)
    )).all()
    members = await family_members(db, family_id)
    runs: dict[str, RoutineRun] = {}
    for r, template, inst in rows:
        run = runs.get(r.id)
        if run is None:
            who = members.get(r.assigned_to)
            run = runs[r.id] = RoutineRun(
                id=r.id, name=r.name, assigned_to=r.assigned_to, start_time=r.start_time, steps=[],
                assigned_name=who.display_name if who else None, assigned_color=who.color_hex if who else None,
            )
        run.steps.append(RoutineRunStep(instance_id=inst.id, template_id=template.id, title=template.title,
                                        minutes=template.minutes or 1, points=template.points, status=inst.status))
    return list(runs.values())


@router.get("/today", response_model=List[RoutineRun])
async def today(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await todays_runs(db, user.family_id)
