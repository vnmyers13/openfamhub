"""Birthdays: each member's next birthday and age, and read-only all-day
calendar entries (they're computed, never stored as events).

29 February birthdays fall on 28 February in other years.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.calendar import CalendarEventResponse

SOURCE_ID = "birthdays"


def on_year(birthday: date, year: int) -> date:
    try:
        return birthday.replace(year=year)
    except ValueError:  # 29 Feb in a non-leap year
        return date(year, 2, 28)


def next_birthday(birthday: date, today: date) -> date:
    this_year = on_year(birthday, today.year)
    return this_year if this_year >= today else on_year(birthday, today.year + 1)


def age_on(birthday: date, day: date) -> int:
    """How old someone born on `birthday` turns on their birthday in `day`'s year."""
    return day.year - birthday.year


@dataclass
class Upcoming:
    user_id: str
    display_name: str
    color_hex: str
    avatar_value: Optional[str]
    date: date
    turns: int
    days_away: int


async def _members(db: AsyncSession, family_id: str) -> list[User]:
    return list((await db.execute(
        select(User).where(User.family_id == family_id, User.is_deleted == False, User.birthday.is_not(None))  # noqa: E712
    )).scalars().all())


async def upcoming(db: AsyncSession, family_id: str, today: date, days: int = 30) -> list[Upcoming]:
    out = []
    for u in await _members(db, family_id):
        nxt = next_birthday(u.birthday, today)
        if (nxt - today).days <= days:
            out.append(Upcoming(user_id=u.id, display_name=u.display_name, color_hex=u.color_hex,
                                avatar_value=u.avatar_value, date=nxt, turns=age_on(u.birthday, nxt),
                                days_away=(nxt - today).days))
    return sorted(out, key=lambda b: (b.days_away, b.display_name.lower()))


async def monthly(db: AsyncSession, family_id: str, today: date) -> list[Upcoming]:
    """All birthdays in the current calendar month, sorted by day of month."""
    first = today.replace(day=1)
    # Last day of month: first of next month minus one day
    if today.month == 12:
        last = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    out = []
    for u in await _members(db, family_id):
        nxt = next_birthday(u.birthday, today)
        if first <= nxt <= last:
            out.append(Upcoming(user_id=u.id, display_name=u.display_name, color_hex=u.color_hex,
                                avatar_value=u.avatar_value, date=nxt, turns=age_on(u.birthday, nxt),
                                days_away=(nxt - today).days))
    return sorted(out, key=lambda b: (b.date.day, b.display_name.lower()))


async def birthday_events(db: AsyncSession, family_id: str, start: datetime, end: datetime) -> list[CalendarEventResponse]:
    """All-day entries for birthdays overlapping [start, end). Read-only: they
    carry an external_uid, which the app treats like a synced event."""
    out = []
    first, last = (start - timedelta(days=1)).date(), (end + timedelta(days=1)).date()
    for u in await _members(db, family_id):
        for year in range(first.year, last.year + 1):
            day = on_year(u.birthday, year)
            if year < u.birthday.year:
                continue
            s = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
            e = s + timedelta(days=1)
            if not (s < end and e > start):
                continue
            age = age_on(u.birthday, day)
            title = f"🎂 {u.display_name}'s birthday" + (f" ({age})" if age > 0 else "")
            out.append(CalendarEventResponse(
                id=f"birthday-{u.id}-{year}", source_id=SOURCE_ID, family_id=family_id,
                external_uid=f"birthday:{u.id}:{year}", title=title, start_dt=s.isoformat(), end_dt=e.isoformat(),
                all_day=True, source_color_hex=u.color_hex,
            ))
    return out
