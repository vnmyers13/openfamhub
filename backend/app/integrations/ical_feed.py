import httpx
from icalendar import Calendar
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


async def fetch_ics_feed(url: str) -> Optional[Calendar]:
    """Fetch and parse an ICS feed from the given URL."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            cal = Calendar.from_ical(response.text)
            return cal
    except Exception as e:
        print(f"Error fetching ICS feed from {url}: {e}")
        return None


def parse_calendar_events(cal: Calendar, source_id: str, color_hex: str) -> list[dict]:
    """Parse events from an ICS calendar into database-ready dicts."""
    events = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        summary = str(component.get("SUMMARY", ""))
        description = str(component.get("DESCRIPTION", ""))
        location = str(component.get("LOCATION", ""))

        dt_start = component.get("DTSTART")
        dt_end = component.get("DTEND")

        if dt_start is None:
            continue

        start_date = dt_start.dt
        all_day = isinstance(start_date, datetime) is False

        if isinstance(start_date, datetime):
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)
            start_time = start_date.isoformat()
        else:
            start_time = start_date.isoformat()

        if dt_end is not None:
            end_date = dt_end.dt
            if isinstance(end_date, datetime):
                if end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=timezone.utc)
                end_time = end_date.isoformat()
            else:
                end_time = end_date.isoformat()
        else:
            end_time = start_time

        external_uid = str(component.get("UID", uuid4()))

        events.append({
            "id": str(uuid4()),
            "source_id": source_id,
            "external_uid": external_uid,
            "title": summary,
            "description": description,
            "location": location,
            "start_time": start_time,
            "end_time": end_time,
            "all_day": all_day,
            "color_hex": color_hex,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "is_deleted": False,
        })

    return events
