import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.config import settings
from app.models.family import Family
from app.models.user import User
from app.schemas.auth import SetupRequest, LoginRequest, PinLoginRequest, UserResponse, SetupStatusResponse
from sqlalchemy import select, func

@pytest.mark.asyncio
class TestAuth:
    @pytest.fixture(autouse=True)
    async def setup_test_env(self, setup_db):
        """Ensures a clean database for each test in this class."""
        pass

    async def test_health_endpoint(self):
        """Test that the health endpoint returns 200 OK and correct version."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok", "version": settings.app_version}

    async def test_setup_flow(self, setup_db):
        """Test: 1. Successful setup creates family and admin user. 2. Second setup fails."""
        setup_data = {
            "family_name": "Test Family",
            "timezone": "UTC",
            "admin_display_name": "Admin User",
            "admin_password": "securepassword123"
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Successful setup
            response = await client.post("/api/auth/setup", json=setup_data)
            assert response.status_code == 200
            user_data = response.json()
            assert user_data["display_name"] == "Admin User"
            assert user_data["role"] == "admin"

            # 2. Second setup fails
            response = await client.post("/api/auth/setup", json=setup_data)
            assert response.status_code == 400
            assert response.json()["detail"] == "Setup already completed"

    async def test_login_flow(self, setup_db):
        """Test: 1. Successful login with admin credentials. 2. Failed login with wrong password."""
        setup_data = {
            "family_name": "Test Family",
            "timezone": "UTC",
            "admin_display_name": "Admin User",
            "admin_password": "securepassword123"
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Setup admin
            await client.post("/api/auth/setup", json=setup_data)

            # 1. Successful login
            login_data = {
                "display_name": "Admin User",
                "password": "securepassword123"
            }
            response = await client.post("/api/auth/login", json=login_data)
            assert response.status_code == 200
            assert response.json()["display_name"] == "Admin User"

            # 2. Failed login (wrong password)
            bad_login_data = {
                "display_name": "Admin User",
                "password": "wrongpassword"
            }
            response = await client.post("/api/auth/login", json=bad_login_data)
            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid credentials"

    async def test_get_me_unauthorized(self):
        """Test that accessing /me without a cookie returns 401."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/auth/me")
            assert response.status_code == 401

    async def test_get_me_authorized(self, setup_db):
        """Test that accessing /me with a valid cookie returns user data."""
        setup_data = {
            "family_name": "Test Family",
            "timezone": "UTC",
            "admin_display_name": "Admin User",
            "admin_password": "securepassword123"
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Setup admin and get token via cookie
            setup_res = await client.post("/api/auth/setup", json=setup_data)
            assert setup_res.status_code == 200

            # 2. Test /me with the cookie from setup
            response = await client.get("/api/auth/me")
            assert response.status_code == 200
            assert response.json()["display_name"] == "Admin User"
