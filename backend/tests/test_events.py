from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user
from app.models import User, Event

client = TestClient(app)


async def override_get_db():
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def override_get_current_user():
    return {"sub": "test-user-id", "role": "admin"}


app.dependency_overrides[get_current_user] = override_get_current_user


def test_list_events_empty():
    response = client.get("/api/events")
    assert response.status_code == 200
    assert response.json() == []


def test_create_event():
    response = client.post(
        "/api/events",
        json={
            "title": "Family Dinner",
            "description": "Monthly family dinner",
            "location": "Home",
            "start_time": "2026-07-01T18:00:00Z",
            "end_time": "2026-07-01T20:00:00Z",
            "is_all_day": False,
            "color_hex": "#3b82f6",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Family Dinner"
    assert data["location"] == "Home"
    assert data["is_all_day"] is False

    # Verify it appears in list
    response = client.get("/api/events")
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["title"] == "Family Dinner"


def test_update_event():
    # Create event
    response = client.post(
        "/api/events",
        json={
            "title": "Original Title",
            "start_time": "2026-07-01T18:00:00Z",
            "end_time": "2026-07-01T20:00:00Z",
        },
    )
    event_id = response.json()["id"]

    # Update event
    response = client.patch(
        f"/api/events/{event_id}",
        json={"title": "Updated Title", "description": "New description"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["description"] == "New description"


def test_delete_event():
    # Create event
    response = client.post(
        "/api/events",
        json={
            "title": "To Delete",
            "start_time": "2026-07-01T18:00:00Z",
            "end_time": "2026-07-01T20:00:00Z",
        },
    )
    event_id = response.json()["id"]

    # Delete event
    response = client.delete(f"/api/events/{event_id}")
    assert response.status_code == 200

    # Verify it's gone from list
    response = client.get("/api/events")
    assert response.json() == []
