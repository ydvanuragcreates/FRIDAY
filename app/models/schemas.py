from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User's chat message")


class ChatResponse(BaseModel):
    response: str = Field(..., description="LLM-generated response")
