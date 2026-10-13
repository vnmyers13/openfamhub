from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.schemas import validators
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import discard_queued
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
    def check_color(cls, x):
        return validators.hex_color(x)


@router.post("/ical", response_model=CalendarSourceResponse, status_code=201)
async def add_ical_source(
    data: CreateIcalSourceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    # The source and its first sync succeed or fail together.
    savepoint = await db.begin_nested()
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

    # One download: the first sync is the reachability check. sync_source runs
    # the SSRF guard on every hop and returns its error instead of raising; on
    # failure nothing is kept: not the source, its sync log, or the queued
    # live-update notice.
    error = await sync_source(source, db)
    if error:
        await savepoint.rollback()
        discard_queued(db)
        raise HTTPException(status_code=400, detail=error)

    await savepoint.commit()
    await db.commit()
    await db.refresh(source)
    return source
