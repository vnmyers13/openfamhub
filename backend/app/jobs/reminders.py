"""The reminder engine (Phase 11): runs every minute and sends Web Push.

For each person with at least one device (push subscription), by their own
choices (Preferences.notifications):
- **Events**: a reminder `event_minutes` before a timed event starts. Off by
  default; "mine" is events they added, "all" is every timed family event
  (feeds included). Never sent once the event has started.
- **Daily**: once a day at `daily_time` (family timezone), today's chores and
  to-dos that are theirs. Nothing due, nothing sent.
- **Reward requests** (admins): a request waiting for a yes.

Each reminder is sent once (`notifications_sent`, unique per person, kind and
reference). Quiet hours are the wall's sleep schedule: nothing is sent then;
daily nudges and waiting requests go out when it ends, event reminders that
fall inside it are skipped. If no device accepted a push it's tried again on
the next run.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.chores import ChoreInstance, ChoreTemplate, Todo
from app.models.family import Family
from app.models.push import NotificationSent, PushSubscription
from app.models.rewards import Redemption
from app.models.user import User
from app.routers.family import sleep_schedule
from app.schemas.family import SleepSchedule
from app.schemas.users import NotificationPrefs, Preferences
from app.services import push as push_svc
from app.services.calendar import get_events_in_range

logger = logging.getLogger(__name__)

session_factory = AsyncSessionLocal  # tests swap this for the test session

LOOKAHEAD = timedelta(minutes=61)  # the longest lead time, plus a minute
REQUEST_WINDOW = timedelta(days=2)  # older waiting requests aren't news


def _zone(name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def in_quiet_hours(schedule: SleepSchedule, local: datetime) -> bool:
    """The wall's sleep schedule; `off` later than `on` means overnight."""
    if not schedule.enabled:
        return False
    t, off, on = local.hour * 60 + local.minute, _minutes(schedule.off), _minutes(schedule.on)
    return (t >= off or t < on) if off > on else off <= t < on


def notification_prefs(user: User) -> NotificationPrefs:
    try:
        return Preferences(**((user.settings_json or {}).get("prefs") or {})).notifications
    except ValueError:
        return NotificationPrefs()


async def _sent(db: AsyncSession, user_id: str, kind: str, ref: str) -> bool:
    return (await db.execute(select(NotificationSent.id).where(
        NotificationSent.user_id == user_id, NotificationSent.kind == kind, NotificationSent.ref == ref))).first() is not None


async def _record(db: AsyncSession, family_id: str, user_id: str, kind: str, ref: str) -> None:
    try:
        async with db.begin_nested():
            db.add(NotificationSent(family_id=family_id, user_id=user_id, kind=kind, ref=ref[:160]))
    except IntegrityError:  # another run got there first
        pass


async def _push(db: AsyncSession, family_id: str, user_id: str, kind: str, ref: str, payload: dict) -> bool:
    if await _sent(db, user_id, kind, ref):
        return False
    if await push_svc.send_to_users(db, [user_id], {**payload, "tag": f"{kind}:{ref}"}) > 0:
        await _record(db, family_id, user_id, kind, ref)
        return True
    return False


async def _event_reminders(db, family: Family, people: list[User], now: datetime, zone: ZoneInfo) -> int:
    wanted = [(u, p) for u in people if (p := notification_prefs(u)).events != "off"]
    if not wanted:
        return 0
    sent = 0
    events = await get_events_in_range(db, family.id, now, now + LOOKAHEAD)
    for ev in events:
        if ev.all_day:
            continue
        start = datetime.fromisoformat(ev.start_dt)
        start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
        if start <= now:
            continue
        for user, prefs in wanted:
            if prefs.events == "mine" and ev.created_by != user.id:
                continue
            if start - timedelta(minutes=prefs.event_minutes) > now:
                continue
            when = start.astimezone(zone).strftime("%H:%M")
            payload = {"title": ev.title, "body": f"Starts at {when}" + (f" · {ev.location}" if ev.location else ""),
                       "url": "/calendar"}
            sent += await _push(db, family.id, user.id, "event", f"{ev.id}@{start.isoformat()}", payload)
    return sent


async def _daily_nudges(db, family: Family, people: list[User], local: datetime) -> int:
    today: date = local.date()
    sent = 0
    for user in people:
        prefs = notification_prefs(user)
        if not prefs.daily or local.hour * 60 + local.minute < _minutes(prefs.daily_time):
            continue
        ref = today.isoformat()
        if await _sent(db, user.id, "daily", ref):
            continue
        chores = (await db.execute(
            select(ChoreTemplate.title)
            .join(ChoreInstance, ChoreInstance.template_id == ChoreTemplate.id)
            .where(ChoreInstance.family_id == family.id, ChoreInstance.due_date == today,
                   ChoreTemplate.routine_id.is_(None), ChoreInstance.status.in_(("pending", "claimed")),
                   or_(ChoreInstance.assigned_to == user.id, ChoreInstance.claimed_by == user.id))
            .order_by(ChoreTemplate.title)
        )).scalars().all()
        todos = (await db.execute(
            select(Todo.title).where(Todo.family_id == family.id, Todo.assigned_to == user.id,
                                     Todo.completed_at.is_(None), Todo.due_date <= today)
            .order_by(Todo.due_date, Todo.title)
        )).scalars().all()
        if not chores and not todos:
            await _record(db, family.id, user.id, "daily", ref)  # nothing due: done for today
            continue
        counts = [f"{len(chores)} chore{'s' if len(chores) != 1 else ''}" if chores else "",
                  f"{len(todos)} to-do{'s' if len(todos) != 1 else ''}" if todos else ""]
        names = ", ".join([*chores, *todos][:6]) + ("…" if len(chores) + len(todos) > 6 else "")
        payload = {"title": f"Today: {' and '.join(c for c in counts if c)}", "body": names, "url": "/chores"}
        sent += await _push(db, family.id, user.id, "daily", ref, payload)
    return sent


async def _reward_requests(db, family: Family, people: list[User], now: datetime) -> int:
    admins = [u for u in people if u.role == "admin" and notification_prefs(u).rewards]
    if not admins:
        return 0
    rows = (await db.execute(
        select(Redemption, User.display_name)
        .join(User, User.id == Redemption.user_id)
        .where(Redemption.family_id == family.id, Redemption.status == "pending",
               Redemption.requested_at >= now - REQUEST_WINDOW)
        .order_by(Redemption.requested_at)
    )).all()
    sent = 0
    for red, who in rows:
        payload = {"title": "Reward request", "body": f"{who} asked for {red.reward_name} ({red.point_cost} points)",
                   "url": "/rewards"}
        for admin in admins:
            sent += await _push(db, family.id, admin.id, "reward", red.id, payload)
    return sent


async def remind_family(db: AsyncSession, family: Family, now: datetime) -> int:
    zone = _zone(family.timezone)
    local = now.astimezone(zone)
    if in_quiet_hours(sleep_schedule(family), local):
        return 0
    people = list((await db.execute(
        select(User).where(User.family_id == family.id, User.is_deleted == False,  # noqa: E712
                           User.id.in_(select(PushSubscription.user_id)))
    )).scalars().all())
    if not people:
        return 0
    return (await _event_reminders(db, family, people, now, zone)
            + await _daily_nudges(db, family, people, local)
            + await _reward_requests(db, family, people, now))


async def run_reminders(now: Optional[datetime] = None) -> int:
    now = now or datetime.now(timezone.utc)
    sent = 0
    async with session_factory() as db:
        families = list((await db.execute(select(Family).where(Family.is_deleted == False))).scalars().all())  # noqa: E712
        for family in families:
            try:
                sent += await remind_family(db, family, now)
            except Exception:  # noqa: BLE001  - one family's trouble shouldn't stop the others
                logger.exception("Reminders failed for a family")
        await db.commit()
    if sent:
        logger.info("Sent %s reminders", sent)
    return sent


def register_reminder_job(scheduler) -> None:
    scheduler.add_job(run_reminders, "interval", minutes=1, id="reminders", replace_existing=True,
                      max_instances=1, coalesce=True)
