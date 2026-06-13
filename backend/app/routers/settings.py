import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.schemas.settings import TimezoneSettingsResponse, VALID_TIMEZONES
from app.models.event import User

router = APIRouter()


@router.get("/timezone", response_model=TimezoneSettingsResponse)
async def get_timezone(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == current_user["sub"]))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    settings = _parse_settings(user.settings_json)
    tz = settings.get("wall_timezone", "UTC") if settings else "UTC"

    return TimezoneSettingsResponse(timezone=tz)


@router.put("/timezone", response_model=TimezoneSettingsResponse)
async def update_timezone(
    req: dict,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    timezone = req.get("timezone", "")

    if timezone not in VALID_TIMEZONES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid timezone. Must be one of: {', '.join(VALID_TIMEZONES)}",
        )

    result = await db.execute(select(User).where(User.id == admin["sub"]))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    current_settings = _parse_settings(user.settings_json) or {}
    current_settings["wall_timezone"] = timezone
    user.settings_json = json.dumps(current_settings)

    await db.flush()

    return TimezoneSettingsResponse(timezone=timezone)


def _parse_settings(settings_json_str: str) -> dict | None:
    """Parse settings from user's settings_json string."""
    try:
        return json.loads(settings_json_str)
    except (json.JSONDecodeError, TypeError):
        return None
