import uuid

from app.db.models.code_change import ChangeType
from app.db.models.execution import ExecutionStatus
from app.db.models.message import MessageRole
from app.db.models.tool_call import ToolCallStatus
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.execution_repository import ExecutionRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.user_repository import UserRepository


async def _make_user(session):
    return await UserRepository(session).create(user_id=uuid.uuid4(), email="dev@example.com", name="Dev")


async def _make_project(session, user_id):
    return await ProjectRepository(session).create(
        user_id=user_id,
        name="Demo",
        description="A demo project",
        repository_path="/workspace/demo",
        repository_url=None,
    )


async def test_user_repository_create_and_get(db_session) -> None:
    user = await _make_user(db_session)

    fetched = await UserRepository(db_session).get_by_id(user.id)
    assert fetched is not None
    assert fetched.email == "dev@example.com"

    by_email = await UserRepository(db_session).get_by_email("dev@example.com")
    assert by_email is not None
    assert by_email.id == user.id


async def test_user_repository_get_by_id_missing_returns_none(db_session) -> None:
    assert await UserRepository(db_session).get_by_id(uuid.uuid4()) is None


async def test_project_repository_create_and_get(db_session) -> None:
    user = await _make_user(db_session)
    project = await _make_project(db_session, user.id)

    fetched = await ProjectRepository(db_session).get_by_id(project.id)
    assert fetched is not None
    assert fetched.name == "Demo"
    assert fetched.user_id == user.id


async def test_project_repository_list_by_user(db_session) -> None:
    user = await _make_user(db_session)
    await _make_project(db_session, user.id)
    await _make_project(db_session, user.id)

    projects = await ProjectRepository(db_session).list_by_user(user.id)
    assert len(projects) == 2


async def test_project_repository_update_applies_only_given_fields(db_session) -> None:
    user = await _make_user(db_session)
    project = await _make_project(db_session, user.id)

    updated = await ProjectRepository(db_session).update(project, {"description": "new description"})

    assert updated.description == "new description"
    assert updated.name == "Demo"  # untouched


async def test_project_repository_delete(db_session) -> None:
    user = await _make_user(db_session)
    project = await _make_project(db_session, user.id)

    await ProjectRepository(db_session).delete(project)

    assert await ProjectRepository(db_session).get_by_id(project.id) is None


async def test_conversation_repository_create_and_messages(db_session) -> None:
    user = await _make_user(db_session)
    project = await _make_project(db_session, user.id)
    conversations = ConversationRepository(db_session)

    conversation = await conversations.create(project_id=project.id, title="First chat")
    await conversations.add_message(conversation_id=conversation.id, role=MessageRole.USER, content="hi")
    await conversations.add_message(
        conversation_id=conversation.id, role=MessageRole.ASSISTANT, content="hello!"
    )

    messages = await conversations.list_messages(conversation.id)
    assert [m.role for m in messages] == [MessageRole.USER, MessageRole.ASSISTANT]

    listed = await conversations.list_by_project(project.id)
    assert len(listed) == 1
    assert listed[0].id == conversation.id


async def test_execution_repository_full_lifecycle(db_session) -> None:
    user = await _make_user(db_session)
    project = await _make_project(db_session, user.id)
    executions = ExecutionRepository(db_session)

    execution_id = uuid.uuid4()
    execution = await executions.create(
        execution_id=execution_id,
        project_id=project.id,
        conversation_id=None,
        user_request="add a feature",
    )
    assert execution.status == ExecutionStatus.PENDING

    await executions.add_plan(execution_id=execution_id, plan="1. do it")
    await executions.add_tool_call(
        execution_id=execution_id,
        tool_name="list_files",
        input={"directory": "."},
        output={"result": "a.py"},
        status=ToolCallStatus.SUCCESS,
    )
    await executions.add_code_change(
        execution_id=execution_id,
        file_path="a.py",
        change_type=ChangeType.CREATE,
        diff="+print(1)",
        approved=True,
        applied=True,
    )
    await executions.add_test_result(
        execution_id=execution_id, command="pytest", passed=True, output="1 passed", error_output=None
    )
    await executions.update_status(execution, status=ExecutionStatus.COMPLETED, retry_count=1)

    detail = await executions.get_detail(execution_id)
    assert detail is not None
    assert detail.status == ExecutionStatus.COMPLETED
    assert detail.retry_count == 1
    assert len(detail.agent_plans) == 1
    assert len(detail.tool_calls) == 1
    assert len(detail.code_changes) == 1
    assert len(detail.test_results) == 1


async def test_execution_repository_list_by_project(db_session) -> None:
    user = await _make_user(db_session)
    project = await _make_project(db_session, user.id)
    executions = ExecutionRepository(db_session)

    await executions.create(execution_id=uuid.uuid4(), project_id=project.id, conversation_id=None, user_request="a")
    await executions.create(execution_id=uuid.uuid4(), project_id=project.id, conversation_id=None, user_request="b")

    listed = await executions.list_by_project(project.id)
    assert len(listed) == 2
