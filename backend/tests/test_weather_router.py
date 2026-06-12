import json
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.security import create_access_token, get_current_user
from app.models.event import User


def _create_user(db: AsyncSession, name: str = "Test User", role: str = "admin", settings_json: str = "{}") -> User:
    user = User(
        name=name,
        avatar_emoji="👤",
        pin_hash="dummy",
        role=role,
        settings_json=settings_json,
    )
    db.add(user)
    return user


@pytest.mark.asyncio
async def test_get_weather_no_settings(test_client, db: AsyncSession):
    user = _create_user(db, settings_json="{}")
    db.add(user)
    await db.commit()

    token = create_access_token(user.id, user.role)
    resp = test_client.get("/api/weather", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] == "location_not_set"
    assert data["settings"]["lat"] == 0
    assert data["settings"]["lon"] == 0


@pytest.mark.asyncio
async def test_get_weather_settings_empty(test_client, db: AsyncSession):
    user = _create_user(db, settings_json="{}")
    db.add(user)
    await db.commit()

    token = create_access_token(user.id, user.role)
    resp = test_client.get("/api/weather/settings", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["lat"] == 0
    assert data["lon"] == 0


@pytest.mark.asyncio
async def test_update_weather_settings(test_client, db: AsyncSession):
    user = _create_user(db, settings_json='{"weather_lat": 0, "weather_lon": 0}')
    db.add(user)
    await db.commit()

    token = create_access_token(user.id, user.role)
    resp = test_client.put(
        "/api/weather/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"lat": 41.8781, "lon": -87.6298, "location_name": "Chicago"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["lat"] == 41.8781
    assert data["lon"] == -87.6298
    assert data["location_name"] == "Chicago"


@pytest.mark.asyncio
async def test_update_weather_settings_validation(test_client, db: AsyncSession):
    user = _create_user(db)
    db.add(user)
    await db.commit()

    token = create_access_token(user.id, user.role)
    resp = test_client.put(
        "/api/weather/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"lat": 100, "lon": -87.6298, "location_name": "Invalid"},
    )

    assert resp.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_weather_settings_non_admin_fails(test_client, db: AsyncSession):
    user = _create_user(db, role="member")
    db.add(user)
    await db.commit()

    token = create_access_token(user.id, user.role)

    def get_real_user():
        return {"sub": user.id, "role": "member"}

    app.dependency_overrides[get_current_user] = get_real_user

    try:
        resp = test_client.put(
            "/api/weather/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={"lat": 41.8781, "lon": -87.6298, "location_name": "Chicago"},
        )

        assert resp.status_code == 403  # Forbidden
    finally:
        app.dependency_overrides[get_current_user] = lambda: {"sub": "test-user-id", "role": "admin"}
