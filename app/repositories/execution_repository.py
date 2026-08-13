import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.agent_plan import AgentPlan
from app.db.models.code_change import ChangeType, CodeChange
from app.db.models.execution import Execution, ExecutionStatus
from app.db.models.test_result import TestResult
from app.db.models.tool_call import ToolCall, ToolCallStatus


class ExecutionRepository:
    """Execution is the aggregate root for one LangGraph run — this
    repository also owns writes to its four child tables (agent_plans,
    tool_calls, code_changes, test_results) rather than splitting those
    into four more repository files for what's always an execution_id-
    scoped insert.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        execution_id: uuid.UUID,
        project_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        user_request: str,
        status: ExecutionStatus = ExecutionStatus.PENDING,
    ) -> Execution:
        execution = Execution(
            id=execution_id,
            project_id=project_id,
            conversation_id=conversation_id,
            user_request=user_request,
            status=status,
        )
        self._session.add(execution)
        await self._session.flush()
        return execution

    async def get_by_id(self, execution_id: uuid.UUID) -> Execution | None:
        return await self._session.get(Execution, execution_id)

    async def get_detail(self, execution_id: uuid.UUID) -> Execution | None:
        result = await self._session.execute(
            select(Execution)
            .options(
                selectinload(Execution.agent_plans),
                selectinload(Execution.tool_calls),
                selectinload(Execution.code_changes),
                selectinload(Execution.test_results),
            )
            .where(Execution.id == execution_id)
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: uuid.UUID) -> list[Execution]:
        result = await self._session.execute(
            select(Execution).where(Execution.project_id == project_id).order_by(Execution.started_at.desc())
        )
        return list(result.scalars())

    async def update_status(
        self,
        execution: Execution,
        *,
        status: ExecutionStatus,
        error_message: str | None = None,
        completed_at: datetime | None = None,
        retry_count: int | None = None,
    ) -> Execution:
        execution.status = status
        if error_message is not None:
            execution.error_message = error_message
        if completed_at is not None:
            execution.completed_at = completed_at
        if retry_count is not None:
            execution.retry_count = retry_count
        await self._session.flush()
        return execution

    async def add_plan(self, *, execution_id: uuid.UUID, plan: str) -> AgentPlan:
        record = AgentPlan(execution_id=execution_id, plan=plan)
        self._session.add(record)
        await self._session.flush()
        return record

    async def add_tool_call(
        self,
        *,
        execution_id: uuid.UUID,
        tool_name: str,
        input: dict[str, Any],
        output: dict[str, Any],
        status: ToolCallStatus,
    ) -> ToolCall:
        record = ToolCall(
            execution_id=execution_id, tool_name=tool_name, input=input, output=output, status=status
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def add_code_change(
        self,
        *,
        execution_id: uuid.UUID,
        file_path: str,
        change_type: ChangeType,
        diff: str,
        approved: bool | None,
        applied: bool,
    ) -> CodeChange:
        record = CodeChange(
            execution_id=execution_id,
            file_path=file_path,
            change_type=change_type,
            diff=diff,
            approved=approved,
            applied=applied,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def add_test_result(
        self,
        *,
        execution_id: uuid.UUID,
        command: str,
        passed: bool,
        output: str,
        error_output: str | None,
    ) -> TestResult:
        record = TestResult(
            execution_id=execution_id, command=command, passed=passed, output=output, error_output=error_output
        )
        self._session.add(record)
        await self._session.flush()
        return record
