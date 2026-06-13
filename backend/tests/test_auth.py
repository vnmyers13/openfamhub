from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db
from app.core.security import get_current_user, decode_access_token
from app.models import User
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from tests.conftest import TestSessionLocal

client = TestClient(app)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


def override_get_current_user():
    return {"sub": "test-user-id", "role": "admin"}


def test_list_profiles():
    response = client.get("/api/auth/profiles")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_login_with_wrong_pin():
    response = client.post("/api/auth/login", json={"pin": "000000"})
    assert response.status_code == 401
    assert "Incorrect PIN" in response.json()["detail"]


def test_create_user_and_login():
    # Create a test user
    response = client.post(
        "/api/users/profiles",
        json={"name": "Test User", "avatar_emoji": "🧑", "pin": "1234", "role": "member"},
    )
    assert response.status_code == 201
    user_data = response.json()
    assert user_data["name"] == "Test User"
    user_id = user_data["id"]

    # Login with the PIN
    response = client.post("/api/auth/login", json={"pin": "1234"})
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["user"]["name"] == "Test User"

    # Verify the token contains the correct user ID
    payload = decode_access_token(token_data["access_token"])
    assert payload["sub"] == user_id

    # Use the token to get profile - temporarily override get_current_user
    def get_real_user():
        return payload

    app.dependency_overrides[get_current_user] = get_real_user

    try:
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Test User"
    finally:
        # Restore original override
        app.dependency_overrides[get_current_user] = override_get_current_user
