"""Phase 12: a routine can start a Home Assistant scene or script at its
start time (family timezone), on the days the routine runs.

Each runs once a day (`settings_json["ha_scene_runs"]`). If Home Assistant
doesn't answer it's tried again on the next run, but only within a few
minutes of the start: lights coming on an hour late would be worse than not
at all.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.family import Family
from app.routers.home_assistant import family_config
from app.routers.routines import todays_runs
from app.services import home_assistant as ha

logger = logging.getLogger(__name__)

session_factory = AsyncSessionLocal  # tests swap this for the test session

GRACE_MINUTES = 5


def _zone(name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


async def _family_scenes(db, family: Family, now: datetime) -> int:
    scenes = family_config(family).routine_scenes
    if not scenes:
        return 0
    local = now.astimezone(_zone(family.timezone))
    today, minute = local.date().isoformat(), local.hour * 60 + local.minute
    done: dict = dict((family.settings_json or {}).get("ha_scene_runs") or {})
    ran = 0
    for run in await todays_runs(db, family.id):
        target = scenes.get(run.id)
        if not target or not run.start_time or done.get(run.id) == today:
            continue
        hh, mm = run.start_time.split(":")
        if not 0 <= minute - (int(hh) * 60 + int(mm)) < GRACE_MINUTES:
            continue
        try:
            await ha.call(target, "turn_on")
        except ha.Unavailable as exc:
            logger.warning("Routine %s: couldn't start %s: %s", run.name, target, exc)
            continue
        done[run.id] = today
        ran += 1
    if ran:
        family.settings_json = {**(family.settings_json or {}), "ha_scene_runs": done}
        await db.flush()
    return ran


async def run_routine_scenes(now: Optional[datetime] = None) -> int:
    if not ha.configured():
        return 0
    now = now or datetime.now(timezone.utc)
    ran = 0
    async with session_factory() as db:
        families = list((await db.execute(select(Family).where(Family.is_deleted == False))).scalars().all())  # noqa: E712
        for family in families:
            try:
                ran += await _family_scenes(db, family, now)
            except Exception:  # noqa: BLE001  - one family's trouble shouldn't stop the others
                logger.exception("Routine scenes failed for a family")
        await db.commit()
    return ran


def register_home_assistant_job(scheduler) -> None:
    scheduler.add_job(run_routine_scenes, "interval", minutes=1, id="ha_routine_scenes", replace_existing=True,
                      max_instances=1, coalesce=True)
