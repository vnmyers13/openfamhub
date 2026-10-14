"""The wall's read-only panels (Phase 10): today's chores, the week's meals,
announcements and the weather for a paired display.

v0.29's panels called the member endpoints, so a wall needed someone's login.
These answer to the display's `wall_token` cookie instead (`get_wall_device`)
and return what a family member sees for the same family. They only read:
a display can't tick a chore or change the plan here. Kept apart from
`wall.py` (pairing, events, routines) and mounted on the same `/api/wall`
prefix, where the cookie is scoped.
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.chores import ChoreInstance, ChoreTemplate
from app.models.family import Family
from app.models.wall_device import WallDevice
from app.routers.announcements import recent, to_announcement
from app.routers.chores import to_instance
from app.routers.meals import _monday, _plan_week, today_for
from app.routers.wall import get_wall_device
from app.routers.weather import weather_for
from app.schemas.chores import ChoreInstanceResponse
from app.schemas.family_info import AnnouncementResponse, WeatherResponse
from app.schemas.meals import PlanWeek

router = APIRouter()

WALL_ANNOUNCEMENTS = 10  # what fits on a panel; pinned ones first


@router.get("/chores", response_model=List[ChoreInstanceResponse])
async def wall_chores(db: AsyncSession = Depends(get_db), device: WallDevice = Depends(get_wall_device)):
    """Today's chores in the family timezone. Routine steps are left out: the routines panel shows them."""
    today = await today_for(db, device.family_id)
    rows = await db.execute(
        select(ChoreInstance, ChoreTemplate)
        .join(ChoreTemplate, ChoreTemplate.id == ChoreInstance.template_id)
        .where(ChoreInstance.family_id == device.family_id, ChoreInstance.due_date == today,
               ChoreTemplate.routine_id.is_(None))
        .order_by(func.lower(ChoreTemplate.title))
    )
    return [to_instance(i, t) for i, t in rows.all()]


@router.get("/meals", response_model=PlanWeek)
async def wall_meals(start: Optional[date] = None, db: AsyncSession = Depends(get_db),
                     device: WallDevice = Depends(get_wall_device)):
    """The meal plan for this week (or the week containing `start`)."""
    return await _plan_week(db, device.family_id, _monday(start, await today_for(db, device.family_id)))


@router.get("/announcements", response_model=List[AnnouncementResponse])
async def wall_announcements(db: AsyncSession = Depends(get_db), device: WallDevice = Depends(get_wall_device)):
    return [to_announcement(a) for a in await recent(db, device.family_id, WALL_ANNOUNCEMENTS)]


@router.get("/weather", response_model=WeatherResponse)
async def wall_weather(db: AsyncSession = Depends(get_db), device: WallDevice = Depends(get_wall_device)):
    family = await db.get(Family, device.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")
    return await weather_for(family)
