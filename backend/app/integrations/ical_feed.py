from datetime import datetime, date, timedelta, timezone
from typing import Any

import httpx
from dateutil.rrule import rrulestr
from icalendar import Calendar as ICalendar


def _to_utc(dt: datetime | date) -> datetime:
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _expand_recurrence(
    vevent: Any,
    uid: str,
    dtstart: datetime,
    dtend: datetime | None,
) -> list[dict]:
    rrule_val = vevent.get("RRULE")
    if not rrule_val:
        return []

    try:
        rule_str = rrule_val.to_ical().decode()
    except Exception:
        return []

    until_limit = datetime.now(timezone.utc) + timedelta(days=365)
    try:
        rule = rrulestr(rule_str, dtstart=dtstart)
    except Exception:
        return []

    occurrences = []
    for occ_dt in rule:
        if occ_dt.tzinfo is None:
            occ_dt = occ_dt.replace(tzinfo=timezone.utc)

        if occ_dt > until_limit:
            break

        occ_start = _to_utc(occ_dt)
        duration = (dtend - dtstart) if dtend else timedelta(hours=1)
        occ_end = occ_start + duration
        occ_uid = f"{uid}_{occ_start.isoformat()}"

        occurrences.append({
            "external_uid": occ_uid,
            "title": str(vevent.get("SUMMARY", "(no title)")),
            "start_dt": occ_start,
            "end_dt": occ_end,
            "all_day": False,
            "location": str(vevent.get("LOCATION", "")) or None,
            "description": str(vevent.get("DESCRIPTION", "")) or None,
        })
    return occurrences


async def fetch_and_parse(url: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        raise ValueError(f"ICS fetch returned HTTP {resp.status_code}")

    calendar = ICalendar.from_ical(resp.content)

    events = []
    for component in calendar.walk():
        if component.name != "VEVENT":
            continue

        uid = str(component.get("UID", ""))
        dtstart_raw = component.get("DTSTART")
        dtend_raw = component.get("DTEND")

        if dtstart_raw is None:
            continue

        start_dt = dtstart_raw.dt
        is_all_day = isinstance(start_dt, date) and not isinstance(start_dt, datetime)
        start = _to_utc(start_dt)

        if dtend_raw is not None:
            end = _to_utc(dtend_raw.dt)
        else:
            duration = component.get("DURATION")
            if duration:
                end = start + duration.dt
            else:
                end = start + timedelta(hours=1)

        event_uid = uid or f"no-uid-{start.isoformat()}"
        base = {
            "external_uid": event_uid,
            "title": str(component.get("SUMMARY", "(no title)")),
            "start_dt": start,
            "end_dt": end,
            "all_day": is_all_day,
            "location": str(component.get("LOCATION", "")) or None,
            "description": str(component.get("DESCRIPTION", "")) or None,
        }
        events.append(base)

        recurrences = _expand_recurrence(component, event_uid, start_dt, dtend_raw.dt if dtend_raw else None)
        events.extend(recurrences)

    return events
