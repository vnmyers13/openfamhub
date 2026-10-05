import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.config import settings
import app.models  # noqa: F401  — registers tables on Base.metadata for create_all

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
        finally:
            await session.close()


@pytest.fixture(scope="function")
async def setup_db(db_engine, db_session):
    """Ensures the database schema is created before each test."""
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield db_session
        # Commit before dropping tables: fixture finalization runs in reverse
        # order, so db_session's teardown runs after this one.
        await db_session.commit()
    except Exception:
        await db_session.rollback()
        raise
    finally:
        await db_session.close()
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def client(setup_db):
    """Provides an AsyncClient with the test database session injected via dependency override."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.database import get_db

    app.dependency_overrides[get_db] = lambda: setup_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)
