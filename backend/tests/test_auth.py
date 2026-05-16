import pytest
from app.core.config import settings


class TestAuth:
    async def test_health_endpoint(self, client):
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": settings.app_version}

    async def test_setup_flow(self, client):
        setup_data = {
            "family_name": "Test Family",
            "timezone": "UTC",
            "admin_display_name": "Admin User",
            "admin_password": "securepassword123",
        }

        response = await client.post("/api/auth/setup", json=setup_data)
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["display_name"] == "Admin User"
        assert user_data["role"] == "admin"

        response = await client.post("/api/auth/setup", json=setup_data)
        assert response.status_code == 400
        assert response.json()["detail"] == "Setup already completed"

    async def test_login_flow(self, client):
        setup_data = {
            "family_name": "Test Family",
            "timezone": "UTC",
            "admin_display_name": "Admin User",
            "admin_password": "securepassword123",
        }

        await client.post("/api/auth/setup", json=setup_data)

        login_data = {
            "display_name": "Admin User",
            "password": "securepassword123",
        }
        response = await client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        assert response.json()["display_name"] == "Admin User"

        bad_login_data = {
            "display_name": "Admin User",
            "password": "wrongpassword",
        }
        response = await client.post("/api/auth/login", json=bad_login_data)
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    async def test_get_me_unauthorized(self, client):
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_get_me_authorized(self, client):
        setup_data = {
            "family_name": "Test Family",
            "timezone": "UTC",
            "admin_display_name": "Admin User",
            "admin_password": "securepassword123",
        }

        setup_res = await client.post("/api/auth/setup", json=setup_data)
        assert setup_res.status_code == 200

        cookie_header = setup_res.headers.get("set-cookie")
        assert cookie_header is not None

        response = await client.get("/api/auth/me", headers={"Cookie": cookie_header})
        assert response.status_code == 200
        assert response.json()["display_name"] == "Admin User"
