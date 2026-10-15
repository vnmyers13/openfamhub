"""The reminder engine (Phase 11): runs every minute.

For each person with a device (push subscription), an ntfy topic or an email
address, by their own choices (Preferences.notifications):
- **Events**: a reminder `event_minutes` before a timed event starts. Off by
  default; "mine" is events they added, "all" is every timed family event
  (feeds included). Never sent once the event has started.
- **Daily**: once a day at `daily_time` (family timezone), today's chores and
  to-dos that are theirs. Nothing due, nothing sent.
- **Reward requests** (admins): a request waiting for a yes.
- **Birthdays**: the day before, at `daily_time`, to everyone but the
  birthday person.
- **Pantry** (members and admins): at `daily_time`, one list of what reaches
  its use-by date today or tomorrow.
- **Allowance**: their weekly allowance was paid.

Reminders go to every channel the person set up: their devices (Web Push),
their ntfy topic and their email address (services/notify.py).

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
from app.models.meals import PantryItem
from app.models.rewards import AllowanceEntry, Redemption
from app.models.user import User
from app.routers.family import sleep_schedule
from app.schemas.family import SleepSchedule
from app.schemas.users import NotificationPrefs
from app.services import notify
from app.services.birthdays import age_on, next_birthday
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


notification_prefs = notify.notification_prefs


async def _sent(db: AsyncSession, user_id: str, kind: str, ref: str) -> bool:
    return (await db.execute(select(NotificationSent.id).where(
        NotificationSent.user_id == user_id, NotificationSent.kind == kind, NotificationSent.ref == ref))).first() is not None


async def _record(db: AsyncSession, family_id: str, user_id: str, kind: str, ref: str) -> None:
    try:
        async with db.begin_nested():
            db.add(NotificationSent(family_id=family_id, user_id=user_id, kind=kind, ref=ref[:160]))
    except IntegrityError:  # another run got there first
        pass


async def _push(db: AsyncSession, family_id: str, user: User, kind: str, ref: str, payload: dict) -> bool:
    if await _sent(db, user.id, kind, ref):
        return False
    if await notify.deliver(db, user, {**payload, "tag": f"{kind}:{ref}"}) > 0:
        await _record(db, family_id, user.id, kind, ref)
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
            sent += await _push(db, family.id, user, "event", f"{ev.id}@{start.isoformat()}", payload)
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
        sent += await _push(db, family.id, user, "daily", ref, payload)
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
            sent += await _push(db, family.id, admin, "reward", red.id, payload)
    return sent


def _morning(prefs: NotificationPrefs, local: datetime) -> bool:
    return local.hour * 60 + local.minute >= _minutes(prefs.daily_time)


async def _birthdays(db, family: Family, people: list[User], local: datetime) -> int:
    tomorrow = local.date() + timedelta(days=1)
    rows = (await db.execute(
        select(User.id, User.display_name, User.birthday)
        .where(User.family_id == family.id, User.is_deleted == False, User.birthday.is_not(None))  # noqa: E712
        .order_by(User.display_name)
    )).all()
    tomorrows = [(uid, name, born) for uid, name, born in rows if next_birthday(born, tomorrow) == tomorrow]
    sent = 0
    for uid, name, born in tomorrows:
        payload = {"title": f"Tomorrow: {name} turns {age_on(born, tomorrow)}", "body": "Their birthday is tomorrow.",
                   "url": "/calendar"}
        for user in people:
            prefs = notification_prefs(user)
            if user.id == uid or not prefs.birthdays or not _morning(prefs, local):
                continue
            sent += await _push(db, family.id, user, "birthday", f"{uid}:{tomorrow.isoformat()}", payload)
    return sent


async def _pantry(db, family: Family, people: list[User], local: datetime) -> int:
    today = local.date()
    wanted = [u for u in people if u.role in ("admin", "member")
              and (p := notification_prefs(u)).pantry and _morning(p, local)]
    if not wanted:
        return 0
    items = (await db.execute(
        select(PantryItem.name, PantryItem.expires_on)
        .where(PantryItem.family_id == family.id, PantryItem.expires_on >= today,
               PantryItem.expires_on <= today + timedelta(days=1))
        .order_by(PantryItem.expires_on, PantryItem.name)
    )).all()
    ref = today.isoformat()
    if not items:
        return 0  # checked again next run, so food added later today still counts
    names = ", ".join(f"{n} ({'today' if d == today else 'tomorrow'})" for n, d in items[:6]) + ("…" if len(items) > 6 else "")
    payload = {"title": f"Use soon: {len(items)} pantry item{'s' if len(items) != 1 else ''}", "body": names,
               "url": "/meals"}
    sent = 0
    for user in wanted:
        sent += await _push(db, family.id, user, "pantry", ref, payload)
    return sent


async def _allowance_paid(db, family: Family, people: list[User], now: datetime) -> int:
    by_id = {u.id: u for u in people if notification_prefs(u).allowance}
    if not by_id:
        return 0
    rows = (await db.execute(
        select(AllowanceEntry)
        .where(AllowanceEntry.family_id == family.id, AllowanceEntry.source_type == "weekly",
               AllowanceEntry.user_id.in_(list(by_id)), AllowanceEntry.created_at >= now - REQUEST_WINDOW)
        .order_by(AllowanceEntry.created_at)
    )).scalars().all()
    sent = 0
    for entry in rows:
        amount = f"${entry.delta_cents / 100:,.2f}"
        week = f" for the week of {entry.week_start.day} {entry.week_start:%b}" if entry.week_start else ""
        payload = {"title": f"Allowance paid: {amount}", "body": f"Your allowance{week} is in.", "url": "/rewards"}
        sent += await _push(db, family.id, by_id[entry.user_id], "allowance", entry.id, payload)
    return sent


async def remind_family(db: AsyncSession, family: Family, now: datetime) -> int:
    zone = _zone(family.timezone)
    local = now.astimezone(zone)
    if in_quiet_hours(sleep_schedule(family), local):
        return 0
    with_device = set((await db.execute(
        select(PushSubscription.user_id).where(PushSubscription.family_id == family.id))).scalars().all())
    members = (await db.execute(
        select(User).where(User.family_id == family.id, User.is_deleted == False)  # noqa: E712
    )).scalars().all()
    people = [u for u in members if u.id in with_device or notify.reachable_without_device(u)]
    if not people:
        return 0
    return (await _event_reminders(db, family, people, now, zone)
            + await _daily_nudges(db, family, people, local)
            + await _reward_requests(db, family, people, now)
            + await _birthdays(db, family, people, local)
            + await _pantry(db, family, people, local)
            + await _allowance_paid(db, family, people, now))


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
