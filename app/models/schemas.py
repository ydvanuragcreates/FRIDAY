from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User's chat message")


class ChatResponse(BaseModel):
    response: str = Field(..., description="LLM-generated response")


class TaskRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Coding task to plan and implement")


class TaskDecisionRequest(BaseModel):
    approved: bool = Field(
        ..., description="Whether the human reviewer approves the proposed changes"
    )


class ProposedChangeResponse(BaseModel):
    file_path: str
    action: str
    content: str
    diff: str


class TaskResponse(BaseModel):
    thread_id: str = Field(..., description="Identifier for this task; use it to submit a decision")
    status: str = Field(..., description="'awaiting_approval' or 'completed'")
    plan: str = ""
    analysis: str = ""
    files_inspected: list[str] = []
    proposed_changes: list[ProposedChangeResponse] = []
    applied_changes: list[str] = []
    test_results: str = ""
    test_passed: bool = False
    retry_count: int = 0
    errors: list[str] = []
    final_response: str = ""


class IndexRequest(BaseModel):
    path: str = Field(
        default=".", description="Directory to index, relative to the workspace root"
    )


class IndexResponse(BaseModel):
    project_id: str
    collection_name: str
    files_indexed: int
    chunks_indexed: int
    errors: list[str] = []
