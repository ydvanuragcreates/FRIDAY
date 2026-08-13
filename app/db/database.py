"""Async engine, session factory, and the two ways the rest of the app
gets a session: `get_db_session` (FastAPI dependency, request-scoped) and
`session_scope` (a bare async context manager for code that runs outside
a request — see app/services/execution_recorder.py for why LangGraph
node execution needs that).
"""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=settings.database_echo, future=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=get_engine(), expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """One self-contained unit of work: commits if the block completes
    without raising, rolls back and re-raises otherwise. Every caller —
    the FastAPI dependency below and every execution_recorder.py
    function — gets that guarantee without repeating the try/except.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request, following the same
    commit-on-success/rollback-on-exception rule as `session_scope`.
    Routes/services never call session.commit() or .rollback() themselves.
    """
    async with session_scope() as session:
        yield session
