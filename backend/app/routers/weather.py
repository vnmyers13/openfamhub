"""Weather (Phase 8): the family's forecast from Open-Meteo, cached ~10 min.

The location is a family setting an admin picks by searching for a place
(Open-Meteo's geocoder); there's no API key. If the forecast can't be fetched
the response says so instead of failing the dashboard.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import queue_event
from app.core.security import get_current_user, require_role
from app.models.family import Family
from app.models.user import User
from app.schemas.family_info import Place, WeatherLocation, WeatherResponse
from app.services import weather as svc

router = APIRouter()


async def _family(db: AsyncSession, user: User) -> Family:
    family = await db.get(Family, user.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")
    return family


def location_of(family: Family) -> WeatherLocation | None:
    stored = (family.settings_json or {}).get("weather")
    try:
        return WeatherLocation(**stored) if stored else None
    except ValueError:
        return None


async def weather_for(family: Family) -> WeatherResponse:
    loc = location_of(family)
    if loc is None:
        return WeatherResponse(configured=False)
    try:
        data = await svc.forecast(loc.latitude, loc.longitude, loc.units, family.timezone or "UTC")
    except Exception:  # noqa: BLE001  - network, HTTP or JSON trouble shouldn't break the page
        return WeatherResponse(configured=True, place=loc.name, units=loc.units, error="Weather is unavailable right now")
    return WeatherResponse(configured=True, place=loc.name, units=loc.units, **data)


@router.get("", response_model=WeatherResponse)
async def get_weather(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await weather_for(await _family(db, user))


@router.get("/location", response_model=WeatherLocation | None)
async def get_location(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return location_of(await _family(db, user))


@router.put("/location", response_model=WeatherLocation)
async def set_location(data: WeatherLocation, db: AsyncSession = Depends(get_db),
                       admin: User = Depends(require_role("admin"))):
    family = await _family(db, admin)
    family.settings_json = {**(family.settings_json or {}), "weather": data.model_dump()}
    await db.flush()
    queue_event(db, "settings_updated", {})
    return data


@router.delete("/location")
async def clear_location(db: AsyncSession = Depends(get_db), admin: User = Depends(require_role("admin"))):
    family = await _family(db, admin)
    family.settings_json = {k: v for k, v in (family.settings_json or {}).items() if k != "weather"}
    await db.flush()
    queue_event(db, "settings_updated", {})
    return {"message": "Weather turned off"}


@router.get("/places", response_model=List[Place])
async def search_places(q: str = Query(..., min_length=2, max_length=100), admin: User = Depends(require_role("admin"))):
    try:
        return await svc.find_places(q)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Couldn't search places right now")
