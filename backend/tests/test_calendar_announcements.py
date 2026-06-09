import pytest
from unittest.mock import AsyncMock, patch


async def test_create_calendar_source(test_client):
    """Test creating a calendar source."""
    payload = {
        "name": "School Calendar",
        "url": "http://example.com/school.ics",
        "color_hex": "#FF5733",
        "sync_interval_hours": 12,
    }

    res = test_client.post("/api/calendar/sources", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "School Calendar"
    assert data["url"] == "http://example.com/school.ics"
    assert data["color_hex"] == "#FF5733"
    assert data["sync_interval_hours"] == 12
    assert data["is_active"] is True


async def test_list_calendar_sources(test_client):
    """Test listing calendar sources (empty by default)."""
    res = test_client.get("/api/calendar/sources")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


async def test_create_announcement(test_client):
    """Test creating an announcement."""
    payload = {"content": "This is a test announcement"}

    res = test_client.post("/api/announcements", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["content"] == "This is a test announcement"
    assert data["is_pinned"] is False


async def test_list_announcements(test_client):
    """Test listing announcements (empty by default)."""
    res = test_client.get("/api/announcements")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


async def test_toggle_pin_announcement(test_client):
    """Test toggling pin on an announcement."""
    # First create an announcement
    create_res = test_client.post("/api/announcements", json={"content": "Pin me"})
    assert create_res.status_code == 201
    ann_id = create_res.json()["id"]

    # Toggle pin (false -> true)
    res = test_client.patch(f"/api/announcements/{ann_id}/pin")
    assert res.status_code == 200
    assert res.json()["message"] == "Announcement pinned"

    # Toggle pin again (true -> false)
    res = test_client.patch(f"/api/announcements/{ann_id}/pin")
    assert res.status_code == 200
    assert res.json()["message"] == "Announcement unpinned"
