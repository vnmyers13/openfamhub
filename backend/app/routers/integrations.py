import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.jobs.calendar_sync import sync_source
from app.models.calendar_source import CalendarSource
from app.models.user import User
from app.schemas.calendar import CalendarSourceResponse

router = APIRouter()


class CreateIcalSourceRequest(BaseModel):
    ics_url: str
    display_name: str
    color_hex: str = "#4F46E5"
    sync_interval_hours: int = 6

    @field_validator("color_hex")
    @classmethod
    def valid_hex(cls, v: str) -> str:
        if not v.startswith("#") or len(v) != 7:
            raise ValueError("color_hex must be #RRGGBB")
        int(v[1:], 16)
        return v


@router.post("/ical", response_model=CalendarSourceResponse, status_code=201)
async def add_ical_source(
    data: CreateIcalSourceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.head(data.ics_url, follow_redirects=True)
        if resp.status_code >= 400:
            raise HTTPException(status_code=400, detail=f"ICS URL returned HTTP {resp.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=400, detail="ICS URL timed out")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=400, detail=f"Could not reach ICS URL: {exc}")

    source = CalendarSource(
        family_id=current_user.family_id,
        provider="ical",
        display_name=data.display_name,
        color_hex=data.color_hex,
        ics_url=data.ics_url,
        sync_interval_hours=float(data.sync_interval_hours),
    )
    db.add(source)
    await db.flush()

    try:
        await sync_source(source, db)
    except Exception:
        pass

    await db.commit()
    await db.refresh(source)
    return source
