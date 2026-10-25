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
- **Wellness** (off unless chosen): a drink of water every 1–3 hours between
  two times, and a breathing pause once a day. Devices and ntfy only, never
  email. One missed by more than a few minutes (quiet hours, downtime) is
  skipped rather than sent late.

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


async def _push(db: AsyncSession, family_id: str, user: User, kind: str, ref: str, payload: dict,
                email: bool = True) -> bool:
    if await _sent(db, user.id, kind, ref):
        return False
    if await notify.deliver(db, user, {**payload, "tag": f"{kind}:{ref}"}, email=email) > 0:
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
    """Day-before, week-before, and day-of birthday notifications.

    - **Day-before** (`birthdays`): "Tomorrow: {name} turns {age}" 7 days before the birthday.
    - **Week-before** (`birthdays_week_before`): "Next week: {name} turns {age}" 7 days before.
    - **Day-of** (`birthdays_day_of`): "Happy Birthday, {name}! (turns {age})" on the birthday.

    The birthday person themselves never receives any of these.
    """
    today = local.date()
    tomorrow = today + timedelta(days=1)
    a_week = today + timedelta(days=7)
    rows = (await db.execute(
        select(User.id, User.display_name, User.birthday)
        .where(User.family_id == family.id, User.is_deleted == False, User.birthday.is_not(None))  # noqa: E712
        .order_by(User.display_name)
    )).all()
    sent = 0
    for uid, name, born in rows:
        nxt = next_birthday(born, today)
        nxt_a_week = next_birthday(born, a_week)
        for user in people:
            prefs = notification_prefs(user)
            if user.id == uid:
                continue  # never notify the birthday person about themselves
            if not _morning(prefs, local):
                continue
            # Day-before: next birthday is tomorrow
            if prefs.birthdays and nxt == tomorrow:
                age = age_on(born, tomorrow)
                payload = {"title": f"Tomorrow: {name} turns {age}", "body": "Their birthday is tomorrow.",
                           "url": "/calendar"}
                sent += await _push(db, family.id, user, "birthday", f"{uid}:{tomorrow.isoformat()}", payload)
            # Week-before: next birthday is 7 days away
            if prefs.birthdays_week_before and nxt_a_week == a_week:
                age = age_on(born, a_week)
                payload = {"title": f"Next week: {name} turns {age}", "body": "Their birthday is next week.",
                           "url": "/calendar"}
                sent += await _push(db, family.id, user, "birthday_week", f"{uid}:{a_week.isoformat()}", payload)
            # Day-of: next birthday is today (and it's the actual birthday day)
            if prefs.birthdays_day_of and nxt == today:
                age = age_on(born, today)
                payload = {"title": f"Happy Birthday, {name}! (turns {age})", "body": "Today is their birthday!",
                           "url": "/calendar"}
                sent += await _push(db, family.id, user, "birthday_day", f"{uid}:{today.isoformat()}", payload)
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


WATER_GRACE = 15  # minutes: later than this after its time, a water reminder is skipped
MINDFUL_GRACE = 30
WATER_LINES = ("A glass of water now keeps you going.", "Time to refill your water bottle.",
               "Take a few sips: your brain is mostly water.", "Water break! Your future self says thanks.")
MINDFUL_LINES = ("Breathe in for four, hold for four, out for four. Three times.",
                 "Drop your shoulders, unclench your jaw, take one slow breath.",
                 "Look out a window for a minute and notice three things.",
                 "Close your eyes and listen: what can you hear?",
                 "Think of one good thing from today.")


async def _wellness(db, family: Family, people: list[User], local: datetime) -> int:
    now_min, today = local.hour * 60 + local.minute, local.date()
    sent = 0
    for user in people:
        prefs = notification_prefs(user)
        if prefs.water:
            start, end = _minutes(prefs.water_from), _minutes(prefs.water_until)
            if start <= now_min <= end:
                slot = start + (now_min - start) // prefs.water_every * prefs.water_every
                if now_min - slot <= WATER_GRACE:
                    line = WATER_LINES[(slot // prefs.water_every) % len(WATER_LINES)]
                    ref = f"{today.isoformat()}@{slot // 60:02d}:{slot % 60:02d}"
                    sent += await _push(db, family.id, user, "water", ref,
                                        {"title": "💧 Time for some water", "body": line, "url": "/"}, email=False)
        if prefs.mindful:
            at = _minutes(prefs.mindful_time)
            if 0 <= now_min - at <= MINDFUL_GRACE:
                line = MINDFUL_LINES[today.toordinal() % len(MINDFUL_LINES)]
                sent += await _push(db, family.id, user, "mindful", today.isoformat(),
                                    {"title": "🧘 A minute to breathe", "body": line, "url": "/"}, email=False)
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
            + await _allowance_paid(db, family, people, now)
            + await _wellness(db, family, people, local))


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
