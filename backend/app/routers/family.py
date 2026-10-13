"""Family settings: name, timezone (used for feeds' floating times and the
wall's sleep schedule) and the wall sleep schedule."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import queue_event
from app.core.security import get_current_user, require_role
from app.models.family import Family
from app.models.user import User
from app.schemas.family import FamilySettings, FamilySettingsUpdate, SleepSchedule

router = APIRouter()


def sleep_schedule(family: Family) -> SleepSchedule:
    stored = (family.settings_json or {}).get("sleep") or {}
    try:
        return SleepSchedule(**stored)
    except ValueError:
        return SleepSchedule()


def to_settings(family: Family) -> FamilySettings:
    return FamilySettings(name=family.name, timezone=family.timezone, sleep=sleep_schedule(family))


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
    await db.flush()
    await db.refresh(family)
    queue_event(db, "settings_updated", {})  # walls re-read their session
    return to_settings(family)
