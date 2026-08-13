"""The only bridge LangGraph nodes use to reach the database. Each
function opens its own short-lived session via `session_scope` (see
app/db/database.py for why: a paused, awaiting-approval execution can
outlive the request that started it, so nodes can't borrow a
request-scoped session) and commits immediately — nodes call these and
never touch SQLAlchemy directly.

Every enum-like argument (`status`, `change_type`, ...) is a plain str
here, converted to the real DB enum internally — so app/graph/nodes.py
never needs to import anything from app.db.models either.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from app.db.database import session_scope
from app.db.models.code_change import ChangeType
from app.db.models.execution import ExecutionStatus
from app.db.models.message import MessageRole
from app.db.models.tool_call import ToolCallStatus
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.execution_repository import ExecutionRepository
from app.services.redaction import redact_tool_io


async def record_plan(execution_id: str, plan: str) -> None:
    async with session_scope() as session:
        await ExecutionRepository(session).add_plan(execution_id=uuid.UUID(execution_id), plan=plan)


async def record_tool_call(
    execution_id: str, tool_name: str, args: dict[str, Any], output: str, *, success: bool
) -> None:
    redacted_args, redacted_output = redact_tool_io(args, output)
    async with session_scope() as session:
        await ExecutionRepository(session).add_tool_call(
            execution_id=uuid.UUID(execution_id),
            tool_name=tool_name,
            input=redacted_args,
            output={"result": redacted_output},
            status=ToolCallStatus.SUCCESS if success else ToolCallStatus.ERROR,
        )


async def record_code_change(
    execution_id: str,
    file_path: str,
    change_type: str,
    diff: str,
    *,
    approved: bool | None,
    applied: bool,
) -> None:
    async with session_scope() as session:
        await ExecutionRepository(session).add_code_change(
            execution_id=uuid.UUID(execution_id),
            file_path=file_path,
            change_type=ChangeType(change_type),
            diff=diff,
            approved=approved,
            applied=applied,
        )


async def record_test_result(
    execution_id: str, command: str, passed: bool, output: str, error_output: str | None
) -> None:
    async with session_scope() as session:
        await ExecutionRepository(session).add_test_result(
            execution_id=uuid.UUID(execution_id),
            command=command,
            passed=passed,
            output=output,
            error_output=error_output,
        )


async def update_execution_status(
    execution_id: str,
    status: str,
    *,
    error_message: str | None = None,
    completed: bool = False,
    retry_count: int | None = None,
) -> None:
    async with session_scope() as session:
        repo = ExecutionRepository(session)
        execution = await repo.get_by_id(uuid.UUID(execution_id))
        if execution is None:
            return
        await repo.update_status(
            execution,
            status=ExecutionStatus(status),
            error_message=error_message,
            completed_at=datetime.now(timezone.utc) if completed else None,
            retry_count=retry_count,
        )


async def record_assistant_message(conversation_id: str, content: str) -> None:
    """Save the assistant's final reply once a *resumed* execution
    completes (AgentService.submit_decision).

    Not called from start_task's completion path — ConversationService
    already saves that message itself right after start_task returns
    (see app/services/conversation_service.py), since it's the one that
    knows about the conversation for that call. submit_decision has no
    such caller above it (it's reached directly via
    POST /api/tasks/{id}/decision, reusing Phase 5's approval endpoint —
    see README), so without this, a message that paused for approval
    would never get its reply saved once approved.
    """
    async with session_scope() as session:
        await ConversationRepository(session).add_message(
            conversation_id=uuid.UUID(conversation_id), role=MessageRole.ASSISTANT, content=content
        )
