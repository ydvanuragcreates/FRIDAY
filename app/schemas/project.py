import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    repository_path: str = Field(..., min_length=1, max_length=1024)
    repository_url: str | None = Field(default=None, max_length=2048)


class ProjectUpdate(BaseModel):
    """All fields optional — PATCH semantics, only supplied fields change."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    repository_path: str | None = Field(default=None, min_length=1, max_length=1024)
    repository_url: str | None = Field(default=None, max_length=2048)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    repository_path: str
    repository_url: str | None
    created_at: datetime
    updated_at: datetime
