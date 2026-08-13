"""Shared FastAPI dependencies for the DB-backed routes."""

import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session
from app.repositories.user_repository import UserRepository

# Fixed until real authentication exists (explicitly out of scope for
# this phase). Every project this mock user owns is a real, correctly
# shaped row — `users.id` is a genuine foreign key target, not a
# placeholder value — so adding auth later is "replace this function's
# body with one that reads a session/JWT" and nothing else changes.
MOCK_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
MOCK_USER_EMAIL = "dev@localhost"
MOCK_USER_NAME = "Local Dev User"


async def get_current_user_id(session: AsyncSession = Depends(get_db_session)) -> uuid.UUID:
    """Get-or-create the mock user, every time — self-healing across a
    freshly migrated database or a reset test DB, at the cost of one
    indexed primary-key lookup per request. Cheap enough not to bother
    caching, and caching it would just be a second place auth could get
    out of sync with the DB later.
    """
    repo = UserRepository(session)
    user = await repo.get_by_id(MOCK_USER_ID)
    if user is None:
        user = await repo.create(user_id=MOCK_USER_ID, email=MOCK_USER_EMAIL, name=MOCK_USER_NAME)
    return user.id
