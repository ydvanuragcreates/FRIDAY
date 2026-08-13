import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session
from app.db.models.project import Project
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectNotFoundError(Exception):
    """Raised when a project_id doesn't correspond to an existing row."""


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ProjectRepository(session)

    async def create_project(self, user_id: uuid.UUID, data: ProjectCreate) -> Project:
        return await self._repo.create(
            user_id=user_id,
            name=data.name,
            description=data.description,
            repository_path=data.repository_path,
            repository_url=data.repository_url,
        )

    async def list_projects(self, user_id: uuid.UUID) -> list[Project]:
        return await self._repo.list_by_user(user_id)

    async def get_project(self, project_id: uuid.UUID) -> Project:
        project = await self._repo.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(f"project '{project_id}' not found")
        return project

    async def update_project(self, project_id: uuid.UUID, data: ProjectUpdate) -> Project:
        project = await self.get_project(project_id)
        updates = data.model_dump(exclude_unset=True)
        return await self._repo.update(project, updates)

    async def delete_project(self, project_id: uuid.UUID) -> None:
        project = await self.get_project(project_id)
        await self._repo.delete(project)


def get_project_service(session: AsyncSession = Depends(get_db_session)) -> ProjectService:
    return ProjectService(session)
