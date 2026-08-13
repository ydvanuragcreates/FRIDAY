import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        description: str | None,
        repository_path: str,
        repository_url: str | None,
    ) -> Project:
        project = Project(
            user_id=user_id,
            name=name,
            description=description,
            repository_path=repository_path,
            repository_url=repository_url,
        )
        self._session.add(project)
        await self._session.flush()
        return project

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    async def list_by_user(self, user_id: uuid.UUID) -> list[Project]:
        result = await self._session.execute(
            select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
        )
        return list(result.scalars())

    async def update(self, project: Project, updates: dict[str, Any]) -> Project:
        """`updates` should already be the caller's exclude-unset fields
        (see ProjectService.update_project) — applied unconditionally, so
        an explicit `None` (e.g. clearing `description`) takes effect
        rather than being silently skipped.
        """
        for field, value in updates.items():
            setattr(project, field, value)
        await self._session.flush()
        return project

    async def delete(self, project: Project) -> None:
        await self._session.delete(project)
        await self._session.flush()
