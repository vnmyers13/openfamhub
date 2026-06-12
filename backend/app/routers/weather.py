import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.schemas.weather import WeatherResponse, WeatherSettingsUpdate, WeatherSettingsResponse
from app.models.event import User
from app.services.weather import fetch_weather

router = APIRouter()


@router.get("", response_model=WeatherResponse)
async def get_weather(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == current_user["sub"]))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    settings = _parse_weather_settings(user.settings_json)

    if settings is None:
        return WeatherResponse(
            temperature=0,
            condition_code=0,
            condition_description="",
            condition_icon="",
            high=0,
            low=0,
            settings=WeatherSettingsResponse(lat=0, lon=0),
            error="location_not_set",
        )

    weather_data = await fetch_weather(settings["lat"], settings["lon"])

    if "error" in weather_data:
        return WeatherResponse(
            temperature=0,
            condition_code=0,
            condition_description="",
            condition_icon="",
            high=0,
            low=0,
            location_name=settings.get("location_name"),
            error=weather_data["error"],
            settings=WeatherSettingsResponse(
                lat=settings["lat"],
                lon=settings["lon"],
                location_name=settings.get("location_name"),
            ),
        )

    return WeatherResponse(
        temperature=weather_data["temperature"],
        condition_code=weather_data["condition_code"],
        condition_description=weather_data["condition_description"],
        condition_icon=weather_data["condition_icon"],
        high=weather_data["high"],
        low=weather_data["low"],
        location_name=settings.get("location_name"),
        settings=WeatherSettingsResponse(
            lat=settings["lat"],
            lon=settings["lon"],
            location_name=settings.get("location_name"),
        ),
    )


@router.get("/settings", response_model=WeatherSettingsResponse)
async def get_weather_settings(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == current_user["sub"]))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    settings = _parse_weather_settings(user.settings_json)

    if settings is None:
        return WeatherSettingsResponse(lat=0, lon=0)

    return WeatherSettingsResponse(
        lat=settings["lat"],
        lon=settings["lon"],
        location_name=settings.get("location_name"),
    )


@router.put("/settings", response_model=WeatherSettingsResponse)
async def update_weather_settings(
    req: WeatherSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == admin["sub"]))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    current_settings = _parse_weather_settings(user.settings_json) or {}
    current_settings["weather_lat"] = req.lat
    current_settings["weather_lon"] = req.lon
    current_settings["weather_location_name"] = req.location_name
    user.settings_json = json.dumps(current_settings)

    await db.flush()

    return WeatherSettingsResponse(
        lat=req.lat,
        lon=req.lon,
        location_name=req.location_name,
    )


def _parse_weather_settings(settings_json_str: str) -> dict | None:
    """Parse weather settings from user's settings_json string."""
    try:
        settings = json.loads(settings_json_str)
    except (json.JSONDecodeError, TypeError):
        return None

    if "weather_lat" not in settings or "weather_lon" not in settings:
        return None

    return {
        "lat": float(settings["weather_lat"]),
        "lon": float(settings["weather_lon"]),
        "location_name": settings.get("weather_location_name"),
    }
