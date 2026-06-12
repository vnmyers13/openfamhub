import asyncio
import pytest
from sqlalchemy import insert
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, create_access_token
from app.models import Chore, ChoreInstance


def override_get_current_user_admin():
    return {"sub": "admin-1", "role": "admin"}


def override_get_current_user_member():
    return {"sub": "test-user-id", "role": "member"}


@pytest.fixture
def admin_user():
    return {
        "id": "admin-1",
        "name": "Admin User",
        "role": "admin",
    }


@pytest.fixture
def chore_template():
    return {
        "id": "chore-1",
        "title": "Dishes",
        "description": "Wash and put away dishes",
        "assignment_mode": "assigned",
        "recurrence_rule": "daily",
        "point_value": 10,
        "created_by_id": "test-user-id",
    }


@pytest.fixture
def chore_instance(chore_template):
    return {
        "id": "instance-1",
        "chore_template_id": chore_template["id"],
        "assigned_to_id": "test-user-id",
        "due_date": "2026-06-12",
        "status": "pending",
    }


def _setup_db():
    from app.core.database import engine
    from app.models.base import Base

    async def _create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_create_tables())


def _insert_chore_data(chore_template, chore_instance):
    from app.core.database import async_session_factory

    async def _do_insert():
        async with async_session_factory() as session:
            stmt = insert(Chore).values(**chore_template)
            await session.execute(stmt)

            stmt2 = insert(ChoreInstance).values(**chore_instance)
            await session.execute(stmt2)
            await session.commit()

    asyncio.get_event_loop().run_until_complete(_do_insert())


def test_admin_can_get_all_instances(
    test_client,
    admin_user,
    chore_template,
    chore_instance,
):
    """Admin should see all chore instances."""
    app.dependency_overrides[get_current_user] = override_get_current_user_admin

    _setup_db()
    _insert_chore_data(chore_template, chore_instance)

    token = create_access_token(admin_user["id"], admin_user["role"])

    response = test_client.get(
        "/api/chores/admin/instances",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["title"] == "Dishes"
    assert data[0]["assigned_to_name"] == "Test Admin"
    assert data[0]["status"] == "pending"

    app.dependency_overrides.clear()


def test_non_admin_cannot_access_admin_endpoint(test_client):
    """Non-admin should get 403."""
    app.dependency_overrides[get_current_user] = override_get_current_user_member

    token = create_access_token("test-user-id", "member")

    response = test_client.get(
        "/api/chores/admin/instances",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403

    app.dependency_overrides.clear()


def test_admin_filter_by_status(
    test_client,
    admin_user,
    chore_template,
    chore_instance,
):
    """Admin should filter instances by status."""
    app.dependency_overrides[get_current_user] = override_get_current_user_admin

    _setup_db()
    _insert_chore_data(chore_template, chore_instance)

    token = create_access_token(admin_user["id"], admin_user["role"])

    response = test_client.get(
        "/api/chores/admin/instances",
        params={"status_filter": "pending"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(item["status"] == "pending" for item in data)

    app.dependency_overrides.clear()


def test_admin_filter_by_date_range(
    test_client,
    admin_user,
    chore_template,
    chore_instance,
):
    """Admin should filter instances by date range."""
    app.dependency_overrides[get_current_user] = override_get_current_user_admin

    _setup_db()
    _insert_chore_data(chore_template, chore_instance)

    token = create_access_token(admin_user["id"], admin_user["role"])

    response = test_client.get(
        "/api/chores/admin/instances",
        params={"start_date": "2026-06-01", "end_date": "2026-06-30"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

    app.dependency_overrides.clear()
