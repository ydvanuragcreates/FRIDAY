import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    SendMessageResponse,
)
from app.services.agent_service import AgentServiceError
from app.services.conversation_service import (
    ConversationNotFoundError,
    ConversationService,
    ProjectNotFoundError,
    get_conversation_service,
)

router = APIRouter()


@router.post(
    "/api/projects/{project_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    project_id: uuid.UUID,
    request: ConversationCreate,
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ConversationResponse:
    try:
        conversation = await conversation_service.create_conversation(project_id, request)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ConversationResponse.model_validate(conversation)


@router.get("/api/projects/{project_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    project_id: uuid.UUID,
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> list[ConversationResponse]:
    try:
        conversations = await conversation_service.list_conversations(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [ConversationResponse.model_validate(c) for c in conversations]


@router.get("/api/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ConversationResponse:
    try:
        conversation = await conversation_service.get_conversation(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ConversationResponse.model_validate(conversation)


@router.get("/api/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: uuid.UUID,
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> list[MessageResponse]:
    try:
        messages = await conversation_service.list_messages(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [MessageResponse.model_validate(m) for m in messages]


@router.post("/api/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_message(
    conversation_id: uuid.UUID,
    request: MessageCreate,
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> SendMessageResponse:
    """Not in the phase spec's explicit endpoint list, but necessary to
    fulfill the send-message flow it describes right after that list —
    the natural POST counterpart to GET .../messages. Runs the full
    LangGraph execution; see README for the request lifecycle, including
    why a code-modifying request comes back 'waiting_for_approval' with
    no assistant_message rather than blocking until a human approves it.
    """
    try:
        result = await conversation_service.send_message(conversation_id, request)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return result
