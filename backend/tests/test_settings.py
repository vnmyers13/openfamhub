import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.main import app


@pytest.fixture
def test_client():
    return TestClient(app)


def test_get_timezone_default(test_client, db):
    """GET /api/settings/timezone returns UTC when no timezone is set."""
    res = test_client.get("/api/settings/timezone")
    assert res.status_code == 200
    data = res.json()
    assert data["timezone"] == "UTC"


@pytest.mark.asyncio
async def test_get_timezone_with_settings(test_client, db: AsyncSession):
    """GET /api/settings/timezone returns stored timezone."""
    await db.execute(
        text("UPDATE users SET settings_json = :settings WHERE id = :uid"),
        {"settings": '{"wall_timezone": "America/New_York"}', "uid": "test-user-id"},
    )
    await db.commit()

    res = test_client.get("/api/settings/timezone")
    assert res.status_code == 200
    data = res.json()
    assert data["timezone"] == "America/New_York"


def test_put_timezone_invalid(test_client, db):
    """PUT /api/settings/timezone with invalid timezone returns 422."""
    res = test_client.put("/api/settings/timezone", json={"timezone": "Invalid/Zone"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_put_timezone_valid(test_client, db: AsyncSession):
    """PUT /api/settings/timezone with valid timezone updates settings."""
    res = test_client.put("/api/settings/timezone", json={"timezone": "America/Los_Angeles"})
    assert res.status_code == 200
    data = res.json()
    assert data["timezone"] == "America/Los_Angeles"

    result = await db.execute(
        text("SELECT settings_json FROM users WHERE id = :uid"),
        {"uid": "test-user-id"},
    )
    row = result.fetchone()
    settings = json.loads(row[0])
    assert settings["wall_timezone"] == "America/Los_Angeles"
