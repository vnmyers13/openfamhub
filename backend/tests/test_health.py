from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db
from app.core.security import get_current_user
from unittest.mock import AsyncMock

client = TestClient(app)


def override_get_db():
    yield AsyncMock()


def override_get_current_user():
    return {"sub": "test-user-id", "role": "admin"}


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
