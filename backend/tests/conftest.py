import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import get_db, async_session_factory
from app.models.user import User
from app.models.event import Event, CalendarSource, CalendarEvent, SyncLog, Announcement
from app.core.security import get_current_user
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def override_get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def override_get_current_user():
    return {"sub": "test-user-id", "role": "admin"}


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user
