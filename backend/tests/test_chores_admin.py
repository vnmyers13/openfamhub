import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, create_access_token
from tests.conftest import override_get_current_user

client = TestClient(app)


def override_get_current_user_admin():
    return {"sub": "test-user-id", "role": "admin"}


def override_get_current_user_member():
    return {"sub": "test-user-id", "role": "member"}


@pytest.fixture
def chore_template_data():
    return {
        "title": "Dishes",
        "description": "Wash and put away dishes",
        "assignment_mode": "assigned",
        "recurrence_rule": "daily",
        "point_value": 10,
    }


async def test_admin_can_get_all_instances(
    db,
    chore_template_data,
):
    """Admin should see all chore instances."""
    app.dependency_overrides[get_current_user] = override_get_current_user_admin

    # Create template via API
    resp = client.post(
        "/api/chores/templates",
        json=chore_template_data,
    )
    assert resp.status_code == 201
    template_id = resp.json()["id"]

    # Create instance directly via DB (instances are created by recurrence system)
    from app.models import ChoreInstance
    from datetime import date

    instance = ChoreInstance(
        chore_template_id=template_id,
        assigned_to_id="test-user-id",
        due_date=date(2026, 6, 12),
        status="pending",
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)

    token = create_access_token("test-user-id", "admin")
    response = client.get(
        "/api/chores/admin/instances",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["title"] == "Dishes"
    assert data[0]["status"] == "pending"

    app.dependency_overrides[get_current_user] = override_get_current_user


def test_non_admin_cannot_access_admin_endpoint():
    """Non-admin should get 403."""
    app.dependency_overrides[get_current_user] = override_get_current_user_member

    token = create_access_token("test-user-id", "member")

    response = client.get(
        "/api/chores/admin/instances",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403

    app.dependency_overrides[get_current_user] = override_get_current_user


async def test_admin_filter_by_status(
    db,
    chore_template_data,
):
    """Admin should filter instances by status."""
    app.dependency_overrides[get_current_user] = override_get_current_user_admin

    # Create template via API
    resp = client.post(
        "/api/chores/templates",
        json=chore_template_data,
    )
    assert resp.status_code == 201
    template_id = resp.json()["id"]

    # Create instance directly via DB
    from app.models import ChoreInstance
    from datetime import date

    instance = ChoreInstance(
        chore_template_id=template_id,
        assigned_to_id="test-user-id",
        due_date=date(2026, 6, 12),
        status="pending",
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)

    token = create_access_token("test-user-id", "admin")
    response = client.get(
        "/api/chores/admin/instances",
        params={"status_filter": "pending"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(item["status"] == "pending" for item in data)

    app.dependency_overrides[get_current_user] = override_get_current_user


async def test_admin_filter_by_date_range(
    db,
    chore_template_data,
):
    """Admin should filter instances by date range."""
    app.dependency_overrides[get_current_user] = override_get_current_user_admin

    # Create template via API
    resp = client.post(
        "/api/chores/templates",
        json=chore_template_data,
    )
    assert resp.status_code == 201
    template_id = resp.json()["id"]

    # Create instance directly via DB
    from app.models import ChoreInstance
    from datetime import date

    instance = ChoreInstance(
        chore_template_id=template_id,
        assigned_to_id="test-user-id",
        due_date=date(2026, 6, 15),
        status="pending",
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)

    token = create_access_token("test-user-id", "admin")
    response = client.get(
        "/api/chores/admin/instances",
        params={"start_date": "2026-06-01", "end_date": "2026-06-30"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

    app.dependency_overrides[get_current_user] = override_get_current_user
