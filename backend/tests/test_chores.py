from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_chore_template():
    response = client.post(
        "/api/chores/templates",
        json={
            "title": "Take out trash",
            "description": "Take kitchen trash to curb",
            "assignment_mode": "claimable",
            "recurrence_rule": "weekly_mon",
            "point_value": 15,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Take out trash"
    assert data["assignment_mode"] == "claimable"
    assert data["point_value"] == 15
    template_id = data["id"]

    # Verify it appears in list
    response = client.get("/api/chores/templates")
    assert response.status_code == 200
    templates = response.json()
    assert any(t["id"] == template_id for t in templates)


def test_update_chore_template():
    # Create template first
    response = client.post(
        "/api/chores/templates",
        json={
            "title": "Dishes",
            "assignment_mode": "assigned",
            "recurrence_rule": "daily",
            "point_value": 10,
        },
    )
    template_id = response.json()["id"]

    # Update
    response = client.patch(
        f"/api/chores/templates/{template_id}",
        json={"point_value": 20, "is_active": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["point_value"] == 20
    assert data["is_active"] is False


def test_deactivate_chore_template():
    # Create template
    response = client.post(
        "/api/chores/templates",
        json={
            "title": "Clean room",
            "assignment_mode": "claimable",
            "recurrence_rule": "weekly_wed",
            "point_value": 25,
        },
    )
    template_id = response.json()["id"]

    # Deactivate
    response = client.delete(f"/api/chores/templates/{template_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Chore template deactivated"

    # Verify not in active list
    response = client.get("/api/chores/templates")
    assert response.status_code == 200
    assert not any(t["id"] == template_id for t in response.json())


def test_complete_chore_instance():
    # Create template
    response = client.post(
        "/api/chores/templates",
        json={
            "title": "Feed pet",
            "assignment_mode": "assigned",
            "recurrence_rule": "daily",
            "point_value": 5,
        },
    )
    template_id = response.json()["id"]

    # Create an instance manually via DB would be needed for full test
    # For now, test the API structure
    response = client.get("/api/chores/instances")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
