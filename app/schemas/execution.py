import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.db.models.code_change import ChangeType
from app.db.models.execution import ExecutionStatus
from app.db.models.tool_call import ToolCallStatus


class AgentPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan: str
    created_at: datetime


class ToolCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tool_name: str
    input: dict[str, Any]
    output: dict[str, Any]
    status: ToolCallStatus
    created_at: datetime


class CodeChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_path: str
    change_type: ChangeType
    diff: str
    approved: bool | None
    applied: bool
    created_at: datetime


class TestResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    command: str
    passed: bool
    output: str
    error_output: str | None
    created_at: datetime


class ExecutionSummary(BaseModel):
    """Row shape for GET /api/projects/{project_id}/executions — a list
    view, no nested children.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    conversation_id: uuid.UUID | None
    status: ExecutionStatus
    user_request: str
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
    retry_count: int


class ExecutionDetail(ExecutionSummary):
    """GET /api/executions/{execution_id} — the full record.

    `agent_plans` is a list of AgentPlanResponse (one per planning round —
    in practice 0 or 1 today, since planner_node runs once per execution)
    rather than a flat list of plan-step strings: that's what's actually
    stored (planner_node's raw text output, per
    app/db/models/agent_plan.py), and a list of records is more honest
    than reshaping one plan's text into fabricated "steps". Named to
    match the ORM relationship it's populated from (Execution.agent_plans)
    so `model_validate(execution, from_attributes=True)` works without
    field aliasing.
    """

    agent_plans: list[AgentPlanResponse] = []
    tool_calls: list[ToolCallResponse] = []
    code_changes: list[CodeChangeResponse] = []
    test_results: list[TestResultResponse] = []
