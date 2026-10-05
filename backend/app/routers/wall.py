"""Wall display pairing and read-only data.

An admin creates a device and gets a one-time pairing URL (/wall?token=...).
The display posts the token to /pair and receives a long-lived httpOnly
cookie. Every /session call refreshes the cookie, so a display that is used
daily never expires; revoking the device in settings cuts it off.
"""
import hashlib
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.family import Family
from app.models.user import User
from app.models.wall_device import WallDevice
from app.schemas.calendar import CalendarEventResponse
from app.services.calendar import get_events_in_range

router = APIRouter()

COOKIE = "wall_token"
# Browsers cap cookie lifetime at ~400 days; it is refreshed on every visit.
COOKIE_MAX_AGE = 400 * 24 * 3600


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE,
        value=token,
        httponly=True,
        samesite="strict",
        secure=True,
        max_age=COOKIE_MAX_AGE,
        path="/api/wall",
    )


async def _device_for_token(db: AsyncSession, token: Optional[str]) -> WallDevice:
    if not token:
        raise HTTPException(status_code=401, detail="Display not paired")
    result = await db.execute(
        select(WallDevice).where(WallDevice.token_hash == _hash(token), WallDevice.revoked == False)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=401, detail="Display not paired")
    return device


async def get_wall_device(
    wall_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> WallDevice:
    return await _device_for_token(db, wall_token)


# ---- admin: manage devices -------------------------------------------------

class CreateDeviceRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_length(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 64:
            raise ValueError("name must be 1-64 characters")
        return v


class DeviceResponse(BaseModel):
    id: str
    name: str
    last_seen_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CreatedDeviceResponse(DeviceResponse):
    token: str


@router.get("/devices", response_model=List[DeviceResponse])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(WallDevice)
        .where(WallDevice.family_id == current_user.family_id, WallDevice.revoked == False)
        .order_by(WallDevice.created_at)
    )
    return list(result.scalars().all())


@router.post("/devices", response_model=CreatedDeviceResponse, status_code=201)
async def create_device(
    data: CreateDeviceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    token = secrets.token_urlsafe(32)
    device = WallDevice(family_id=current_user.family_id, name=data.name, token_hash=_hash(token))
    db.add(device)
    await db.flush()
    await db.refresh(device)
    return CreatedDeviceResponse(
        id=device.id, name=device.name, created_at=device.created_at, token=token
    )


@router.delete("/devices/{device_id}")
async def revoke_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(WallDevice).where(
            WallDevice.id == device_id,
            WallDevice.family_id == current_user.family_id,
            WallDevice.revoked == False,
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Display not found")
    device.revoked = True
    await db.flush()
    return {"ok": True}


# ---- display: pair and read ------------------------------------------------

class PairRequest(BaseModel):
    token: str


@router.post("/pair")
async def pair(data: PairRequest, response: Response, db: AsyncSession = Depends(get_db)):
    device = await _device_for_token(db, data.token)
    device.last_seen_at = datetime.now(timezone.utc)
    _set_cookie(response, data.token)
    return {"ok": True, "name": device.name}


@router.get("/session")
async def session(
    response: Response,
    wall_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    device = await _device_for_token(db, wall_token)
    device.last_seen_at = datetime.now(timezone.utc)
    _set_cookie(response, wall_token)  # sliding expiry
    family = await db.get(Family, device.family_id)
    return {"device": device.name, "family_name": family.name if family else None}


@router.get("/events", response_model=List[CalendarEventResponse])
async def wall_events(
    start: datetime = Query(...),
    end: datetime = Query(...),
    db: AsyncSession = Depends(get_db),
    device: WallDevice = Depends(get_wall_device),
):
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return await get_events_in_range(db, device.family_id, start, end)


class WallMember(BaseModel):
    id: str
    display_name: str
    color_hex: str


@router.get("/members", response_model=List[WallMember])
async def wall_members(
    db: AsyncSession = Depends(get_db),
    device: WallDevice = Depends(get_wall_device),
):
    result = await db.execute(
        select(User)
        .where(User.family_id == device.family_id, User.is_deleted == False)
        .order_by(User.display_name)
    )
    return [
        WallMember(id=u.id, display_name=u.display_name, color_hex=u.color_hex)
        for u in result.scalars().all()
    ]
