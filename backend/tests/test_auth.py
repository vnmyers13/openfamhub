import pytest
from app.core.config import settings


class TestAuth:
    async def test_health_endpoint(self, client):
        response = await client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["version"] == settings.app_version
        assert body["build"].startswith(settings.app_version) or body["build"] == "dev"

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

    async def test_setup_created_admin_profile_id_can_pin_login(self, client):
        setup_res = await client.post("/api/auth/setup", json={
            "family_name": "Test Family",
            "timezone": "UTC",
            "admin_display_name": "Admin User",
            "admin_password": "securepassword123",
            "admin_pin": "1357",
        })
        assert setup_res.status_code == 200
        created_id = setup_res.json()["id"]

        profiles_res = await client.get("/api/auth/profiles")
        assert profiles_res.status_code == 200
        profiles = profiles_res.json()
        assert profiles[0]["id"] == created_id

        login_res = await client.post("/api/auth/login/pin", json={"user_id": profiles[0]["id"], "pin": "1357"})
        assert login_res.status_code == 200
        assert login_res.json()["id"] == created_id

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
