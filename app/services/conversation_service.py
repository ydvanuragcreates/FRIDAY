import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session
from app.db.models.conversation import Conversation
from app.db.models.execution import ExecutionStatus
from app.db.models.message import Message, MessageRole
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.execution_repository import ExecutionRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.conversation import ConversationCreate, MessageCreate, MessageResponse, SendMessageResponse
from app.services.agent_service import AgentService, get_agent_service


class ProjectNotFoundError(Exception):
    """Raised when a conversation is requested for a project_id that
    doesn't exist.
    """


class ConversationNotFoundError(Exception):
    """Raised when a conversation_id doesn't correspond to an existing row."""


class ConversationService:
    def __init__(self, session: AsyncSession, agent_service: AgentService) -> None:
        self._session = session
        self._conversations = ConversationRepository(session)
        self._projects = ProjectRepository(session)
        self._executions = ExecutionRepository(session)
        self._agent_service = agent_service

    async def create_conversation(self, project_id: uuid.UUID, data: ConversationCreate) -> Conversation:
        if await self._projects.get_by_id(project_id) is None:
            raise ProjectNotFoundError(f"project '{project_id}' not found")
        return await self._conversations.create(project_id=project_id, title=data.title)

    async def list_conversations(self, project_id: uuid.UUID) -> list[Conversation]:
        if await self._projects.get_by_id(project_id) is None:
            raise ProjectNotFoundError(f"project '{project_id}' not found")
        return await self._conversations.list_by_project(project_id)

    async def get_conversation(self, conversation_id: uuid.UUID) -> Conversation:
        conversation = await self._conversations.get_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(f"conversation '{conversation_id}' not found")
        return conversation

    async def list_messages(self, conversation_id: uuid.UUID) -> list[Message]:
        await self.get_conversation(conversation_id)
        return await self._conversations.list_messages(conversation_id)

    async def send_message(self, conversation_id: uuid.UUID, data: MessageCreate) -> SendMessageResponse:
        """Save the user message, create+run an execution for it, save the
        assistant reply if the run completed outright. See README > the
        conversation-message request lifecycle for the full picture,
        including why a code-modifying request instead comes back
        'waiting_for_approval' with no assistant_message yet.
        """
        conversation = await self.get_conversation(conversation_id)

        user_message = await self._conversations.add_message(
            conversation_id=conversation_id, role=MessageRole.USER, content=data.content
        )

        execution_id = uuid.uuid4()
        await self._executions.create(
            execution_id=execution_id,
            project_id=conversation.project_id,
            conversation_id=conversation_id,
            user_request=data.content,
            status=ExecutionStatus.RUNNING,
        )
        # The graph's own persistence (execution_recorder.py) runs in
        # independent sessions, keyed by this execution_id — they need
        # the row to be COMMITTED, not just flushed in this session,
        # before the graph starts, or their first write would violate the
        # foreign key (or a slower DB might just not see it yet). The
        # request-scoped session's usual end-of-request commit (see
        # get_db_session) happens too late — start_task runs first.
        await self._session.commit()

        result = await self._agent_service.start_task(
            data.content,
            project_id=str(conversation.project_id),
            conversation_id=str(conversation_id),
            execution_id=str(execution_id),
        )

        assistant_message = None
        if result["status"] == "completed" and result.get("final_response"):
            assistant_message = await self._conversations.add_message(
                conversation_id=conversation_id, role=MessageRole.ASSISTANT, content=result["final_response"]
            )

        return SendMessageResponse(
            conversation_id=conversation_id,
            execution_id=execution_id,
            status=result["status"],
            user_message=MessageResponse.model_validate(user_message),
            assistant_message=MessageResponse.model_validate(assistant_message) if assistant_message else None,
        )


def get_conversation_service(
    session: AsyncSession = Depends(get_db_session),
    agent_service: AgentService = Depends(get_agent_service),
) -> ConversationService:
    return ConversationService(session, agent_service)
