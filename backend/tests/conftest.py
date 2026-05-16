import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.config import settings

# Use an in-memory SQLite database for testing to ensure isolation and speed
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def db_engine():
    """Creates a single async engine for the entire test session."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    yield engine
    import asyncio
    asyncio.run(engine.dispose())

@pytest.fixture(scope="function")
async def db_session(db_engine):
    """Provides a clean, transactional session for each test function."""
    async_session = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

@pytest.fixture(scope="function")
async def setup_db(db_engine, db_session):
    """Ensures the database schema is created before each test."""
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db_session
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def client(db_session):
    """Provides an AsyncClient with the test database session injected via dependency override."""
    from fastapi.testclient import TestClient
    from httpx import AsyncClient
    from app.main import app
    from app.core.database import get_db

    # Override the dependency to use our test session
    app.dependency_overrides[get_db] = lambda: db_session

    # We use AsyncClient for async testing
    return AsyncClient(app=app, base_url="http://test")
