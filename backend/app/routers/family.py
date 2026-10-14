"""Family settings: name, timezone (used for feeds' floating times and the
wall's sleep schedule), the wall sleep schedule and extra wall clocks."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import queue_event
from app.core.security import get_current_user, require_role
from app.models.family import Family
from app.models.user import User
from app.schemas.family import FamilySettings, FamilySettingsUpdate, SleepSchedule, WorldClock

router = APIRouter()


def sleep_schedule(family: Family) -> SleepSchedule:
    stored = (family.settings_json or {}).get("sleep") or {}
    try:
        return SleepSchedule(**stored)
    except ValueError:
        return SleepSchedule()


def world_clocks(family: Family) -> list[WorldClock]:
    """Extra wall clocks (Phase 10). A stored one that no longer validates is skipped."""
    out = []
    for stored in (family.settings_json or {}).get("clocks") or []:
        try:
            out.append(WorldClock(**stored))
        except (TypeError, ValueError):
            continue
    return out


def to_settings(family: Family) -> FamilySettings:
    return FamilySettings(name=family.name, timezone=family.timezone, sleep=sleep_schedule(family),
                          clocks=world_clocks(family))


async def _family(db: AsyncSession, user: User) -> Family:
    family = await db.get(Family, user.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")
    return family


@router.get("", response_model=FamilySettings)
async def get_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return to_settings(await _family(db, current_user))


@router.patch("", response_model=FamilySettings)
async def update_settings(
    data: FamilySettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    family = await _family(db, current_user)
    if data.name is not None:
        family.name = data.name
    if data.timezone is not None:
        family.timezone = data.timezone
    if data.sleep is not None:
        # Reassign the dict so SQLAlchemy sees the JSON column change.
        family.settings_json = {**(family.settings_json or {}), "sleep": data.sleep.model_dump()}
    if data.clocks is not None:
        family.settings_json = {**(family.settings_json or {}), "clocks": [c.model_dump() for c in data.clocks]}
    await db.flush()
    await db.refresh(family)
    queue_event(db, "settings_updated", {})  # walls re-read their session
    return to_settings(family)
