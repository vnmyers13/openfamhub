import sys
import os

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import event, insert

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.security import get_current_user, hash_pin
from app.main import app

# Test user ID used in overrides
TEST_USER_ID = "test-user-id"

# Create in-memory SQLite engine for tests
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
)

# Enable foreign keys for SQLite
@event.listens_for(test_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


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


def override_get_current_user():
    return {"sub": TEST_USER_ID, "role": "admin"}


app.dependency_overrides[get_current_user] = override_get_current_user


@pytest.fixture(scope="function", autouse=True)
async def setup_db():
    """Create tables and default test user before each test."""
    from app.models.base import Base
    from app.models import User

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create default test user
    async with TestSessionLocal() as session:
        stmt = insert(User).values(
            id=TEST_USER_ID,
            name="Test Admin",
            avatar_emoji="👨‍💼",
            pin_hash=hash_pin("0000"),
            role="admin",
            settings_json="{}",
            is_active=True,
        )
        await session.execute(stmt)
        await session.commit()

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# Patch the database module to use test engine
import app.core.database as db_module
db_module.engine = test_engine
db_module.async_session_factory = TestSessionLocal

client = TestClient(app)
