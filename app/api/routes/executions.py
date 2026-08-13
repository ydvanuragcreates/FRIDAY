import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.execution import ExecutionDetail, ExecutionSummary
from app.services.execution_service import (
    ExecutionNotFoundError,
    ExecutionService,
    ProjectNotFoundError,
    get_execution_service,
)

router = APIRouter()


@router.get("/api/projects/{project_id}/executions", response_model=list[ExecutionSummary])
async def list_executions(
    project_id: uuid.UUID,
    execution_service: ExecutionService = Depends(get_execution_service),
) -> list[ExecutionSummary]:
    try:
        executions = await execution_service.list_by_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [ExecutionSummary.model_validate(e) for e in executions]


@router.get("/api/executions/{execution_id}", response_model=ExecutionDetail)
async def get_execution(
    execution_id: uuid.UUID,
    execution_service: ExecutionService = Depends(get_execution_service),
) -> ExecutionDetail:
    """Full execution record — plan, tool calls, code changes, and test
    results — the shape the future "Agent Activity / History" screen
    will read.
    """
    try:
        execution = await execution_service.get_detail(execution_id)
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ExecutionDetail.model_validate(execution)
