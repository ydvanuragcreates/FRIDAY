import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
    """Data access only — no business rules. The mock-user policy (get or
    create a single fixed user until real auth exists) lives in
    app/services/user_service.py, not here.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, *, user_id: uuid.UUID, email: str, name: str) -> User:
        user = User(id=user_id, email=email, name=name)
        self._session.add(user)
        await self._session.flush()
        return user
