"""Recurring iCal expansion (review backlog #4)."""
from datetime import datetime, timezone

import httpx

from app.integrations.ical_feed import fetch_and_parse

PUBLIC_IP = "93.184.216.34"
# Fixed clock: the sample events (October 2026) must stay inside the storage window.
NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)


def _ics(*event_lines: str) -> bytes:
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//OpenFamHub test//EN",
        "BEGIN:VEVENT", *event_lines, "END:VEVENT", "END:VCALENDAR", "",
    ]
    return "\r\n".join(lines).encode()


async def _parse(content: bytes) -> list[dict]:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=content))
    return await fetch_and_parse(f"http://{PUBLIC_IP}/calendar.ics", transport=transport, now=NOW)


def _starts(events: list[dict]) -> list[str]:
    return sorted(e["start_dt"].isoformat() for e in events)


async def test_timed_recurrence_does_not_duplicate_the_first_occurrence():
    events = await _parse(_ics(
        "UID:weekly-timed",
        "DTSTART:20261007T130000Z",
        "DTEND:20261007T150000Z",
        "RRULE:FREQ=WEEKLY;COUNT=3",
        "SUMMARY:Piano",
    ))

    assert _starts(events) == [
        "2026-10-07T13:00:00+00:00",
        "2026-10-14T13:00:00+00:00",
        "2026-10-21T13:00:00+00:00",
    ]
    assert len({e["external_uid"] for e in events}) == 3
    # The first occurrence keeps the series UID, so existing rows stay matched.
    first = min(events, key=lambda e: e["start_dt"])
    assert first["external_uid"] == "weekly-timed"
    assert all(e["end_dt"] - e["start_dt"] == first["end_dt"] - first["start_dt"] for e in events)
    assert all(e["all_day"] is False for e in events)


async def test_all_day_recurrence_keeps_all_day_on_every_occurrence():
    events = await _parse(_ics(
        "UID:weekly-all-day",
        "DTSTART;VALUE=DATE:20261007",
        "DTEND;VALUE=DATE:20261008",
        "RRULE:FREQ=WEEKLY;COUNT=3",
        "SUMMARY:Early release",
    ))

    assert _starts(events) == [
        "2026-10-07T00:00:00+00:00",
        "2026-10-14T00:00:00+00:00",
        "2026-10-21T00:00:00+00:00",
    ]
    for event in events:
        assert event["all_day"] is True
        assert (event["end_dt"] - event["start_dt"]).days == 1


async def test_all_day_recurrence_without_end_lasts_one_day():
    events = await _parse(_ics(
        "UID:daily-all-day-no-end",
        "DTSTART;VALUE=DATE:20261007",
        "RRULE:FREQ=DAILY;COUNT=2",
        "SUMMARY:Spirit week",
    ))

    assert _starts(events) == ["2026-10-07T00:00:00+00:00", "2026-10-08T00:00:00+00:00"]
    for event in events:
        assert event["all_day"] is True
        assert (event["end_dt"] - event["start_dt"]).days == 1


async def test_timed_recurrence_without_end_lasts_one_hour():
    events = await _parse(_ics(
        "UID:daily-timed-no-end",
        "DTSTART:20261007T130000Z",
        "RRULE:FREQ=DAILY;COUNT=2",
        "SUMMARY:Standup",
    ))

    assert len(events) == 2
    for event in events:
        assert (event["end_dt"] - event["start_dt"]).total_seconds() == 3600


async def test_all_day_recurrence_accepts_a_utc_until():
    # Many feeds pair an all-day DTSTART with a UTC UNTIL timestamp.
    events = await _parse(_ics(
        "UID:weekly-all-day-utc-until",
        "DTSTART;VALUE=DATE:20261007",
        "DTEND;VALUE=DATE:20261008",
        "RRULE:FREQ=WEEKLY;UNTIL=20261021T000000Z",
        "SUMMARY:Library day",
    ))

    assert _starts(events) == [
        "2026-10-07T00:00:00+00:00",
        "2026-10-14T00:00:00+00:00",
        "2026-10-21T00:00:00+00:00",
    ]
    assert all(e["all_day"] is True for e in events)
