import uuid

from app.db.database import session_scope
from app.db.models.execution import Execution, ExecutionStatus
from app.repositories.execution_repository import ExecutionRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.user_repository import UserRepository
from app.services.execution_recorder import (
    record_code_change,
    record_plan,
    record_test_result,
    record_tool_call,
    update_execution_status,
)


async def _make_execution(db_engine) -> uuid.UUID:
    execution_id = uuid.uuid4()
    async with session_scope() as session:
        user = await UserRepository(session).create(user_id=uuid.uuid4(), email="dev@example.com", name="Dev")
        project = await ProjectRepository(session).create(
            user_id=user.id, name="Demo", description=None, repository_path="/workspace", repository_url=None
        )
        await ExecutionRepository(session).create(
            execution_id=execution_id, project_id=project.id, conversation_id=None, user_request="do it"
        )
    return execution_id


async def test_record_plan_persists_row(db_engine) -> None:
    execution_id = await _make_execution(db_engine)

    await record_plan(str(execution_id), "1. inspect\n2. implement")

    async with session_scope() as session:
        detail = await ExecutionRepository(session).get_detail(execution_id)
    assert [p.plan for p in detail.agent_plans] == ["1. inspect\n2. implement"]


async def test_record_tool_call_redacts_before_persisting(db_engine) -> None:
    execution_id = await _make_execution(db_engine)

    await record_tool_call(
        str(execution_id),
        "read_file",
        {"file_path": ".env"},
        "ANTHROPIC_API_KEY=sk-ant-secretvalue",
        success=True,
    )

    async with session_scope() as session:
        detail = await ExecutionRepository(session).get_detail(execution_id)
    assert len(detail.tool_calls) == 1
    call = detail.tool_calls[0]
    assert "sk-ant-secretvalue" not in call.output["result"]
    assert call.status.value == "success"


async def test_record_code_change_maps_action_to_change_type(db_engine) -> None:
    execution_id = await _make_execution(db_engine)

    await record_code_change(
        str(execution_id), "app/new.py", "create", "+print(1)", approved=True, applied=True
    )

    async with session_scope() as session:
        detail = await ExecutionRepository(session).get_detail(execution_id)
    assert detail.code_changes[0].change_type.value == "create"
    assert detail.code_changes[0].approved is True
    assert detail.code_changes[0].applied is True


async def test_record_test_result_persists_pass_and_fail_fields(db_engine) -> None:
    execution_id = await _make_execution(db_engine)

    await record_test_result(str(execution_id), "pytest", False, "1 failed", "AssertionError: boom")

    async with session_scope() as session:
        detail = await ExecutionRepository(session).get_detail(execution_id)
    result = detail.test_results[0]
    assert result.passed is False
    assert result.error_output == "AssertionError: boom"


async def test_update_execution_status_sets_completed_fields(db_engine) -> None:
    execution_id = await _make_execution(db_engine)

    await update_execution_status(str(execution_id), "completed", completed=True, retry_count=2)

    async with session_scope() as session:
        execution = await session.get(Execution, execution_id)
    assert execution.status == ExecutionStatus.COMPLETED
    assert execution.retry_count == 2
    assert execution.completed_at is not None


async def test_update_execution_status_is_noop_for_unknown_execution(db_engine) -> None:
    # Should not raise even though this id was never created.
    await update_execution_status(str(uuid.uuid4()), "failed", error_message="boom", completed=True)
