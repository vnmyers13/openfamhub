from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from dateutil.rrule import rrulestr
from icalendar import Calendar as ICalendar

from app.core.safe_fetch import fetch_public

# Real family/school feeds are well under 1 MB; refuse anything absurd.
MAX_ICS_BYTES = 10_000_000

# Only events overlapping [now - WINDOW_PAST, now + WINDOW_FUTURE] are stored.
WINDOW_PAST = timedelta(days=90)
WINDOW_FUTURE = timedelta(days=365)

UTC = timezone.utc


# ---- time helpers ---------------------------------------------------------
#
# Feeds carry three kinds of time:
#   * dates (VALUE=DATE): all-day, stored as 00:00Z of that date;
#   * zoned times (TZID=... or a trailing Z): real instants;
#   * floating times (neither): wall-clock time "wherever you are", which for
#     a family calendar means the family's timezone.
# icalendar 5 hands back pytz zones. pytz needs localize()/normalize(), so
# rrule arithmetic on them keeps the DTSTART offset and drifts an hour at DST
# changes. Zoned times are therefore converted to zoneinfo before expanding.

def _family_zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _is_date(value: Any) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _zoned(dt: datetime, family_tz: ZoneInfo) -> datetime:
    """A timed value as an aware datetime whose tzinfo does DST correctly."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=family_tz)  # floating
    name = getattr(dt.tzinfo, "zone", None) or getattr(dt.tzinfo, "key", None)
    if name and name != "UTC":
        try:
            return dt.replace(tzinfo=None).replace(tzinfo=ZoneInfo(name))
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return dt.astimezone(UTC)


def _instant(value: date | datetime, family_tz: ZoneInfo) -> datetime:
    """Any DTSTART/DTEND/EXDATE/RECURRENCE-ID value as an aware UTC datetime."""
    if _is_date(value):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    return _zoned(value, family_tz).astimezone(UTC)


def _date_values(prop: Any) -> Iterable[date | datetime]:
    """Values of a possibly-repeated, possibly-comma-separated date property."""
    if prop is None:
        return []
    props = prop if isinstance(prop, list) else [prop]
    out = []
    for p in props:
        out.extend(v.dt for v in getattr(p, "dts", []))
    return out


def _times(component: Any, family_tz: ZoneInfo, default: timedelta | None = None):
    """(start_utc, end_utc, all_day, raw_dtstart) for a VEVENT, or None."""
    dtstart = component.get("DTSTART")
    if dtstart is None:
        return None
    raw = dtstart.dt
    all_day = _is_date(raw)
    start = _instant(raw, family_tz)
    dtend = component.get("DTEND")
    duration = component.get("DURATION")
    if dtend is not None:
        end = _instant(dtend.dt, family_tz)
    elif duration is not None:
        end = start + duration.dt
    elif default is not None:
        end = start + default
    else:
        end = start + (timedelta(days=1) if all_day else timedelta(hours=1))
    return start, end, all_day, raw


def _occurrence_starts(component: Any, raw: date | datetime, all_day: bool, family_tz: ZoneInfo,
                       after: datetime, before: datetime) -> list[datetime]:
    """UTC starts of the RRULE occurrences with after <= start <= before."""
    rrule_val = component.get("RRULE")
    if not rrule_val:
        return []
    try:
        rule_str = rrule_val.to_ical().decode()
    except Exception:
        return []

    if all_day:
        # Naive midnight keeps each occurrence on its date; an aware UTC start
        # is needed when the rule's UNTIL is a UTC timestamp.
        candidates = [datetime(raw.year, raw.month, raw.day),
                      datetime(raw.year, raw.month, raw.day, tzinfo=UTC)]
    else:
        zoned = _zoned(raw, family_tz)
        # Aware first; a floating UNTIL needs a naive start in the same zone.
        candidates = [zoned, zoned.replace(tzinfo=None)]

    for rule_start in candidates:
        try:
            rule = rrulestr(rule_str, dtstart=rule_start)
        except Exception:
            continue
        zone = UTC if all_day else _zoned(raw, family_tz).tzinfo
        if rule_start.tzinfo is None:
            lo = after.astimezone(zone).replace(tzinfo=None)
            hi = before.astimezone(zone).replace(tzinfo=None)
            local = rule.between(lo, hi, inc=True)
            return [d.replace(tzinfo=zone).astimezone(UTC) for d in local]
        return [d.astimezone(UTC) for d in rule.between(after, before, inc=True)]
    return []


def _cancelled(component: Any) -> bool:
    return str(component.get("STATUS", "")).upper() == "CANCELLED"


def _event(component: Any, uid: str, start: datetime, end: datetime, all_day: bool) -> dict:
    return {
        "external_uid": uid,
        "title": str(component.get("SUMMARY", "(no title)")),
        "start_dt": start,
        "end_dt": end,
        "all_day": all_day,
        "location": str(component.get("LOCATION", "")) or None,
        "description": str(component.get("DESCRIPTION", "")) or None,
    }


def _instance_uid(uid: str, series_start: datetime | None, start: datetime) -> str:
    # The DTSTART occurrence keeps the series UID; the others get a suffix.
    return uid if start == series_start else f"{uid}_{start.isoformat()}"


def parse_ics(content: bytes, *, family_tz: str | None = "UTC", now: datetime | None = None) -> list[dict]:
    """Parse an ICS payload into event dicts inside the storage window.

    - Recurring events expand within the window only; EXDATEs are removed,
      RDATEs added, and RECURRENCE-ID overrides replace (or, if CANCELLED,
      drop) the instance they name, keeping that instance's external_uid.
    - Floating times are read in ``family_tz``.
    """
    zone = _family_zone(family_tz)
    now = now or datetime.now(UTC)
    window_start, window_end = now - WINDOW_PAST, now + WINDOW_FUTURE
    in_window = lambda s, e: e > window_start and s < window_end  # noqa: E731

    calendar = ICalendar.from_ical(content)
    masters: dict[str, Any] = {}
    overrides: dict[str, dict[datetime, Any]] = {}
    for component in calendar.walk("VEVENT"):
        if component.get("DTSTART") is None:
            continue
        uid = str(component.get("UID", "")) or f"no-uid-{_instant(component['DTSTART'].dt, zone).isoformat()}"
        rid = component.get("RECURRENCE-ID")
        if rid is not None:
            overrides.setdefault(uid, {})[_instant(rid.dt, zone)] = component
        elif uid not in masters:
            masters[uid] = component

    events: dict[str, dict] = {}

    for uid, component in masters.items():
        if _cancelled(component):
            continue
        start, end, all_day, raw = _times(component, zone)
        duration = end - start
        replaced = overrides.get(uid, {})

        if not component.get("RRULE") and not component.get("RDATE"):
            if start not in replaced and in_window(start, end):
                events[uid] = _event(component, uid, start, end, all_day)
            continue

        starts = set(_occurrence_starts(component, raw, all_day, zone, window_start - duration, window_end))
        starts.add(start)  # DTSTART is always an instance
        starts |= {_instant(v, zone) for v in _date_values(component.get("RDATE"))}
        starts -= {_instant(v, zone) for v in _date_values(component.get("EXDATE"))}
        for occ in sorted(starts):
            if occ in replaced or not in_window(occ, occ + duration):
                continue
            key = _instance_uid(uid, start, occ)
            events[key] = _event(component, key, occ, occ + duration, all_day)

    for uid, by_rid in overrides.items():
        master = masters.get(uid)
        series_start = _times(master, zone)[0] if master is not None else None
        default = None
        if master is not None:
            m_start, m_end, _, _ = _times(master, zone)
            default = m_end - m_start
        for rid_start, component in by_rid.items():
            if _cancelled(component) or (master is not None and _cancelled(master)):
                continue
            start, end, all_day, _ = _times(component, zone, default)
            if not in_window(start, end):
                continue
            key = _instance_uid(uid, series_start, rid_start)
            events[key] = _event(component, key, start, end, all_day)

    return list(events.values())


def normalize_ics_url(url: str) -> str:
    """webcal:// is just http(s) with a calendar-app hint."""
    if url.lower().startswith("webcal://"):
        return "https://" + url[len("webcal://"):]
    return url


async def fetch_ics_bytes(
    url: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bytes:
    """Fetch an ICS payload safely (SSRF guard, pinned connection, size cap;
    see core.safe_fetch)."""
    return await fetch_public(
        normalize_ics_url(url), max_bytes=MAX_ICS_BYTES, fetch_label="ICS fetch", size_label="ICS feed",
        transport=transport,
    )


async def fetch_and_parse(
    url: str,
    *,
    transport=None,
    family_tz: str | None = "UTC",
    now: datetime | None = None,
) -> list[dict]:
    content = await fetch_ics_bytes(url, transport=transport)
    return parse_ics(content, family_tz=family_tz, now=now)
