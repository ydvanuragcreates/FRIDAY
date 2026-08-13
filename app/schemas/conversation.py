import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.message import MessageRole


class ConversationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime


class SendMessageResponse(BaseModel):
    """What POST /api/conversations/{id}/messages returns. `status`
    mirrors the underlying execution's status — 'waiting_for_approval'
    means `assistant_message` isn't written yet; approve or reject via
    POST /api/tasks/{execution_id}/decision (execution_id doubles as the
    LangGraph thread_id — see README) to get the rest of the run.
    """

    conversation_id: uuid.UUID
    execution_id: uuid.UUID
    status: str
    user_message: MessageResponse
    assistant_message: MessageResponse | None = None
