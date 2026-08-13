import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session
from app.db.models.execution import Execution
from app.repositories.execution_repository import ExecutionRepository
from app.repositories.project_repository import ProjectRepository


class ExecutionNotFoundError(Exception):
    """Raised when an execution_id doesn't correspond to an existing row."""


class ProjectNotFoundError(Exception):
    """Raised when executions are listed for a project_id that doesn't exist."""


class ExecutionService:
    """Read side of the execution history API — GET .../executions and
    GET /api/executions/{id}. Writes happen incrementally, during the
    graph run itself, via app/services/execution_recorder.py, not here.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._repo = ExecutionRepository(session)
        self._projects = ProjectRepository(session)

    async def list_by_project(self, project_id: uuid.UUID) -> list[Execution]:
        if await self._projects.get_by_id(project_id) is None:
            raise ProjectNotFoundError(f"project '{project_id}' not found")
        return await self._repo.list_by_project(project_id)

    async def get_detail(self, execution_id: uuid.UUID) -> Execution:
        execution = await self._repo.get_detail(execution_id)
        if execution is None:
            raise ExecutionNotFoundError(f"execution '{execution_id}' not found")
        return execution


def get_execution_service(session: AsyncSession = Depends(get_db_session)) -> ExecutionService:
    return ExecutionService(session)
