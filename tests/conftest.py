import pytest
import pytest_asyncio

import app.db.models  # noqa: F401 — populates Base.metadata before create_all
from app.core.config import get_settings
from app.db.base import Base
from app.db.database import get_engine, get_session_factory


@pytest_asyncio.fixture
async def db_engine(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """A fresh SQLite database per test — this dev environment has no
    Postgres server to test against (see README > "Testing without a
    local Postgres server"), so the automated suite substitutes SQLite
    via aiosqlite. Models avoid Postgres-only types for exactly this
    reason (sqlalchemy.Uuid, JSON, and native_enum=False Enum all work
    identically on both dialects).
    """
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """A single session for tests that talk to repositories directly.
    Route-level tests instead let the app build its own per-request
    session against the same (already-migrated) db_engine.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    """A TestClient wired to the real app, talking to `db_engine` — the
    app's own get_db_session dependency builds sessions from the same
    (monkeypatched) DATABASE_URL, so no dependency_overrides are needed.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)
