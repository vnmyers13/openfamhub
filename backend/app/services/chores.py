"""Chore scheduling: when chores are due, and creating their instances.

Due dates are family-local dates. Recurrence is anchored to each template's
start date (v0.29 restarted "every N days" from today on every run, so a
daily run produced an instance every day) and expanded with dateutil's rrule,
the same engine the iCal feeds use. Dates carry no time of day, so DST can
neither repeat nor skip one.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import DAILY, MONTHLY, WEEKLY, rrule, weekday
from dateutil.rrule import MO, TU, WE, TH, FR, SA, SU
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chores import ChoreInstance, ChoreTemplate

HORIZON_DAYS = 7  # instances exist from today to a week ahead
WEEKDAYS: dict[str, weekday] = {"mo": MO, "tu": TU, "we": WE, "th": TH, "fr": FR, "sa": SA, "su": SU}
_FREQ = {"day": DAILY, "week": WEEKLY, "month": MONTHLY}
OPEN = ("pending", "claimed")


def family_today(tz_name: str | None, now: datetime | None = None) -> date:
    """Today's date where the family lives (UTC if the zone is unknown)."""
    try:
        zone = ZoneInfo(tz_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    return (now or datetime.now(timezone.utc)).astimezone(zone).date()


def due_dates(repeat: dict | None, start: date, window_start: date, window_end: date) -> list[date]:
    """Due dates in [window_start, window_end] for a schedule starting on `start`."""
    lo = max(window_start, start)
    if lo > window_end:
        return []
    every = (repeat or {}).get("every", "none")
    if every not in _FREQ:  # a one-off chore is due on its start date
        return [start] if lo <= start <= window_end else []
    kwargs: dict = {"interval": max(1, int(repeat.get("interval") or 1))}
    if every == "week" and repeat.get("weekdays"):
        kwargs["byweekday"] = [WEEKDAYS[d] for d in repeat["weekdays"] if d in WEEKDAYS]
    if every == "month":
        kwargs["bymonthday"] = int(repeat.get("month_day") or start.day)
    rule = rrule(_FREQ[every], dtstart=datetime(start.year, start.month, start.day), **kwargs)
    hits = rule.between(datetime(lo.year, lo.month, lo.day), datetime(window_end.year, window_end.month, window_end.day), inc=True)
    return [d.date() for d in hits]


async def generate_instances(db: AsyncSession, family_id: str, today: date, horizon_days: int = HORIZON_DAYS,
                             template_ids: list[str] | None = None) -> int:
    """Create missing instances from today to the horizon and mark earlier
    unfinished ones missed. Safe to run any number of times: rows that already
    exist are skipped, and (template_id, due_date) is unique in the database."""
    await db.execute(
        update(ChoreInstance)
        .where(ChoreInstance.family_id == family_id, ChoreInstance.due_date < today, ChoreInstance.status.in_(OPEN))
        .values(status="missed")
        .execution_options(synchronize_session="fetch")
    )
    query = select(ChoreTemplate).where(ChoreTemplate.family_id == family_id, ChoreTemplate.is_active == True)  # noqa: E712
    if template_ids is not None:
        query = query.where(ChoreTemplate.id.in_(template_ids))
    templates = list((await db.execute(query)).scalars().all())
    end = today + timedelta(days=horizon_days - 1)
    rows = [
        {"family_id": family_id, "template_id": t.id, "due_date": d, "status": "pending",
         "assigned_to": t.assigned_to if t.assignment == "assigned" else None}
        for t in templates
        for d in due_dates(t.repeat, t.start_date, today, end)
    ]
    if not rows:
        return 0
    result = await db.execute(
        insert(ChoreInstance).values(rows).on_conflict_do_nothing(index_elements=["template_id", "due_date"])
    )
    return result.rowcount or 0


async def _drop_open_future(db: AsyncSession, template_id: str, today: date) -> None:
    await db.execute(
        delete(ChoreInstance)
        .where(ChoreInstance.template_id == template_id, ChoreInstance.due_date >= today, ChoreInstance.status.in_(OPEN))
        .execution_options(synchronize_session="fetch")
    )


async def retire_template(db: AsyncSession, template: ChoreTemplate, today: date) -> None:
    """Stop a chore: no new instances, and today's and later open ones go.
    Completed and missed instances stay for the history."""
    template.is_active = False
    await _drop_open_future(db, template.id, today)
    await db.flush()


async def reschedule_template(db: AsyncSession, template: ChoreTemplate, today: date) -> None:
    """After a template changes: rebuild its open instances from today on."""
    await _drop_open_future(db, template.id, today)
    await db.flush()
    if template.is_active:
        await generate_instances(db, template.family_id, today, template_ids=[template.id])
