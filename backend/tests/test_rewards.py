from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_reward():
    response = client.post(
        "/api/rewards/catalog",
        json={
            "name": "Extra screen time",
            "description": "30 minutes of screen time",
            "point_cost": 50,
            "is_auto_fulfill": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Extra screen time"
    assert data["point_cost"] == 50
    assert data["is_auto_fulfill"] is True
    reward_id = data["id"]

    # Verify in catalog
    response = client.get("/api/rewards/catalog")
    assert response.status_code == 200
    assert any(r["id"] == reward_id for r in response.json())


def test_get_points_balance_empty():
    response = client.get("/api/rewards/points/balance")
    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == 0
    assert len(data["transactions"]) == 0


def test_get_allowance_balance_empty():
    response = client.get("/api/rewards/allowance/balance")
    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == 0.0
    assert len(data["transactions"]) == 0


def test_get_streak_empty():
    response = client.get("/api/rewards/streak")
    assert response.status_code == 200
    data = response.json()
    assert data["current_streak"] == 0
    assert data["longest_streak"] == 0


def test_list_badge_definitions():
    response = client.get("/api/rewards/badge-definitions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
