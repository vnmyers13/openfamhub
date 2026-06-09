import pytest
from unittest.mock import AsyncMock, patch
from icalendar import Calendar, Event as IcsEvent
from datetime import datetime, timezone

from app.integrations.ical_feed import fetch_ics_feed, parse_calendar_events


def create_mock_ics():
    """Create a mock ICS calendar string."""
    cal = Calendar()
    cal.add("prodid", "-//Test//Test//EN")
    cal.add("version", "2.0")

    event = IcsEvent()
    event.add("summary", "Test Event")
    event.add("description", "Test Description")
    event.add("location", "Test Location")
    event.add("uid", "test-event-1@test.com")
    event.add("dtstart", datetime(2026, 7, 1, 10, 0, 0))
    event.add("dtend", datetime(2026, 7, 1, 11, 0, 0))
    cal.add_component(event)

    return cal.to_ical().decode("utf-8")


@patch("app.integrations.ical_feed.httpx.AsyncClient")
async def test_fetch_ics_feed_success(mock_client_class):
    """Test fetching a valid ICS feed."""
    mock_response = AsyncMock()
    mock_response.text = create_mock_ics()
    mock_response.raise_for_status = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

    cal = await fetch_ics_feed("http://example.com/calendar.ics")
    assert cal is not None
    assert len(list(cal.walk())) > 0


@patch("app.integrations.ical_feed.httpx.AsyncClient")
async def test_fetch_ics_feed_failure(mock_client_class):
    """Test fetching an invalid ICS feed returns None."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("Connection error")
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

    cal = await fetch_ics_feed("http://invalid.com/calendar.ics")
    assert cal is None


def test_parse_calendar_events():
    """Test parsing events from an ICS calendar."""
    cal = Calendar()
    cal.add("prodid", "-//Test//Test//EN")
    cal.add("version", "2.0")

    event = IcsEvent()
    event.add("summary", "Test Event")
    event.add("description", "Test Description")
    event.add("location", "Test Location")
    event.add("uid", "test-event-1@test.com")
    event.add("dtstart", datetime(2026, 7, 1, 10, 0, 0))
    event.add("dtend", datetime(2026, 7, 1, 11, 0, 0))
    cal.add_component(event)

    events = parse_calendar_events(cal, "source-1", "#FF5733")

    assert len(events) == 1
    assert events[0]["title"] == "Test Event"
    assert events[0]["description"] == "Test Description"
    assert events[0]["location"] == "Test Location"
    assert events[0]["source_id"] == "source-1"
    assert events[0]["color_hex"] == "#FF5733"
    assert events[0]["all_day"] is False
    assert events[0]["external_uid"] == "test-event-1@test.com"
    assert "start_time" in events[0]
    assert "end_time" in events[0]
    assert events[0]["is_deleted"] is False


def test_parse_calendar_events_empty():
    """Test parsing an empty calendar returns no events."""
    cal = Calendar()
    cal.add("prodid", "-//Test//Test//EN")
    cal.add("version", "2.0")

    events = parse_calendar_events(cal, "source-1", "#FF5733")
    assert len(events) == 0


def test_parse_calendar_events_without_end_time():
    """Test parsing events without DTEND."""
    cal = Calendar()
    cal.add("prodid", "-//Test//Test//EN")
    cal.add("version", "2.0")

    event = IcsEvent()
    event.add("summary", "Event No End")
    event.add("uid", "test-event-2@test.com")
    event.add("dtstart", datetime(2026, 7, 2, 14, 0, 0))
    cal.add_component(event)

    events = parse_calendar_events(cal, "source-1", "#FF5733")
    assert len(events) == 1
    assert events[0]["title"] == "Event No End"
    assert events[0]["end_time"] == events[0]["start_time"]


def test_parse_calendar_events_all_day():
    """Test parsing all-day events."""
    cal = Calendar()
    cal.add("prodid", "-//Test//Test//EN")
    cal.add("version", "2.0")

    event = IcsEvent()
    event.add("summary", "All Day Event")
    event.add("uid", "test-event-3@test.com")
    event.add("dtstart", datetime(2026, 7, 3).date())
    event.add("dtend", datetime(2026, 7, 4).date())
    cal.add_component(event)

    events = parse_calendar_events(cal, "source-1", "#FF5733")
    assert len(events) == 1
    assert events[0]["all_day"] is True
