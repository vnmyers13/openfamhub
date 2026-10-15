"""Phase 12: Home Assistant entities as family cards.

An admin picks which entities the family sees (and which scene or script a
routine runs at its start time); everyone signed in sees their states;
members and admins can switch them. The wall reads the same states through
/api/wall/home-assistant (routers/wall_panels.py). Choices live in
`family.settings_json["home_assistant"]`.
"""
import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.chores import Routine
from app.models.family import Family
from app.models.user import User
from app.services import home_assistant as ha

router = APIRouter()

MAX_ENTITIES = 24
_ENTITY = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


class HAConfig(BaseModel):
    entities: list[str] = Field(default_factory=list)
    routine_scenes: dict[str, str] = Field(default_factory=dict)  # routine id -> scene.* or script.*

    @field_validator("entities")
    @classmethod
    def entity_ids(cls, v: list[str]) -> list[str]:
        if len(v) > MAX_ENTITIES:
            raise ValueError(f"choose up to {MAX_ENTITIES} entities")
        if len(set(v)) != len(v):
            raise ValueError("each entity once")
        for e in v:
            if not _ENTITY.match(e) or ha.domain_of(e) not in ha.SUPPORTED:
                raise ValueError(f"{e} isn't an entity OpenFamHub can show")
        return v

    @model_validator(mode="after")
    def scenes(self) -> "HAConfig":
        for target in self.routine_scenes.values():
            if not _ENTITY.match(target) or ha.domain_of(target) not in ha.RUNNABLE:
                raise ValueError("a routine can run a scene or a script")
        return self


class HAAction(BaseModel):
    entity_id: str
    action: Literal["toggle", "turn_on", "turn_off", "set_temperature", "set_brightness", "set_hvac_mode"]
    temperature: Optional[float] = None
    brightness: Optional[int] = Field(default=None, ge=1, le=100)  # percent
    hvac_mode: Optional[str] = Field(default=None, max_length=32)


def family_config(family: Optional[Family]) -> HAConfig:
    try:
        return HAConfig(**((family.settings_json or {}).get("home_assistant") or {})) if family else HAConfig()
    except ValueError:
        return HAConfig()


async def _family(db: AsyncSession, family_id: str) -> Optional[Family]:
    return await db.get(Family, family_id)


async def family_states(db: AsyncSession, family_id: str) -> dict:
    """What the cards show. Never raises: an unreachable Home Assistant is a message."""
    if not ha.configured():
        return {"configured": False, "available": False, "error": None, "entities": []}
    config = family_config(await _family(db, family_id))
    try:
        entities = await ha.states_for(config.entities) if config.entities else []
    except ha.Unavailable as exc:
        return {"configured": True, "available": False, "error": str(exc), "entities": []}
    return {"configured": True, "available": True, "error": None, "entities": entities}


@router.get("/status")
async def status(user: User = Depends(get_current_user)):
    if not ha.configured():
        return {"configured": False, "reachable": False, "error": None}
    try:
        await ha.check()
    except ha.Unavailable as exc:
        return {"configured": True, "reachable": False, "error": str(exc)}
    return {"configured": True, "reachable": True, "error": None}


@router.get("/entities")
async def entities(admin: User = Depends(require_role("admin"))):
    """Everything an admin can choose from, by kind then name."""
    try:
        states = await ha.all_states()
    except ha.Unavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    found = [ha.brief(s) for s in states if ha.domain_of(s["entity_id"]) in ha.SUPPORTED]
    return sorted(found, key=lambda e: (e["domain"], e["name"].lower()))


@router.get("/config", response_model=HAConfig)
async def get_config(db: AsyncSession = Depends(get_db), admin: User = Depends(require_role("admin"))):
    return family_config(await _family(db, admin.family_id))


@router.put("/config", response_model=HAConfig)
async def put_config(data: HAConfig, db: AsyncSession = Depends(get_db), admin: User = Depends(require_role("admin"))):
    if data.routine_scenes:
        ours = set((await db.execute(select(Routine.id).where(
            Routine.family_id == admin.family_id, Routine.is_active == True))).scalars().all())  # noqa: E712
        if not set(data.routine_scenes) <= ours:
            raise HTTPException(status_code=400, detail="That routine isn't one of this family's")
    family = await _family(db, admin.family_id)
    family.settings_json = {**(family.settings_json or {}), "home_assistant": data.model_dump()}
    await db.flush()
    return data


@router.get("/states")
async def states(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await family_states(db, user.family_id)


@router.post("/action")
async def action(data: HAAction, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in ("admin", "member"):
        raise HTTPException(status_code=403, detail="Viewers can't switch things")
    if not ha.configured():
        raise HTTPException(status_code=409, detail="Home Assistant isn't set up on this server.")
    config = family_config(await _family(db, user.family_id))
    if data.entity_id not in config.entities:
        raise HTTPException(status_code=404, detail="That isn't one of the family's chosen entities")
    if data.action not in ha.CONTROLS.get(ha.domain_of(data.entity_id), set()):
        raise HTTPException(status_code=400, detail="That can't be done to this entity")
    extra: dict = {}
    service = data.action
    if data.action in ("set_brightness", "set_hvac_mode"):
        try:
            current = await ha.state_of(data.entity_id)
        except ha.Unavailable as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        if data.action == "set_brightness":
            if data.brightness is None:
                raise HTTPException(status_code=400, detail="Give a brightness from 1 to 100")
            if not current.get("dimmable"):
                raise HTTPException(status_code=400, detail="That light can't be dimmed")
            service, extra = "turn_on", {"brightness_pct": data.brightness}
        else:
            if data.hvac_mode not in (current.get("hvac_modes") or []):
                raise HTTPException(status_code=400, detail="That thermostat doesn't have that mode")
            extra = {"hvac_mode": data.hvac_mode}
    if data.action == "set_temperature":
        if data.temperature is None:
            raise HTTPException(status_code=400, detail="Give a temperature")
        try:
            current = await ha.state_of(data.entity_id)
        except ha.Unavailable as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        low, high = current.get("min_temp", 5), current.get("max_temp", 35)
        if not low <= data.temperature <= high:
            raise HTTPException(status_code=400, detail=f"Choose between {low:g} and {high:g}")
        extra["temperature"] = data.temperature
    try:
        await ha.call(data.entity_id, service, **extra)
        return await ha.state_of(data.entity_id)
    except ha.Unavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc))


async def family_history(db: AsyncSession, family_id: str, entity_id: str) -> dict:
    if not ha.configured():
        raise HTTPException(status_code=409, detail="Home Assistant isn't set up on this server.")
    if entity_id not in family_config(await _family(db, family_id)).entities:
        raise HTTPException(status_code=404, detail="That isn't one of the family's chosen entities")
    if ha.domain_of(entity_id) != "sensor":
        raise HTTPException(status_code=400, detail="History is for sensors")
    try:
        state = await ha.state_of(entity_id)
        return {**await ha.history(entity_id), "unit": state.get("unit")}
    except ha.Unavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/history/{entity_id}")
async def history(entity_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """A chosen sensor's last day, for its trend line."""
    return await family_history(db, user.family_id, entity_id)
