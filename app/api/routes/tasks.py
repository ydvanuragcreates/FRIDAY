from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import TaskDecisionRequest, TaskRequest, TaskResponse
from app.services.agent_service import (
    AgentService,
    AgentServiceError,
    TaskNotAwaitingApprovalError,
    TaskNotFoundError,
    get_agent_service,
)

router = APIRouter()


@router.post("/api/tasks", response_model=TaskResponse)
async def create_task(
    request: TaskRequest,
    agent_service: AgentService = Depends(get_agent_service),
) -> TaskResponse:
    """Start a code-modification task: planner -> repository analysis ->
    implementation plan, then pause for human approval before anything is
    written to disk. The response's `status` is 'awaiting_approval' with
    `proposed_changes` (each including a diff) to review, or 'completed'
    if the request turned out not to need any code change.
    """
    try:
        result = await agent_service.start_task(request.message)
    except AgentServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return TaskResponse(**result)


@router.get("/api/tasks/{thread_id}", response_model=TaskResponse)
async def get_task(
    thread_id: str,
    agent_service: AgentService = Depends(get_agent_service),
) -> TaskResponse:
    try:
        result = await agent_service.get_task_status(thread_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return TaskResponse(**result)


@router.post("/api/tasks/{thread_id}/decision", response_model=TaskResponse)
async def submit_task_decision(
    thread_id: str,
    request: TaskDecisionRequest,
    agent_service: AgentService = Depends(get_agent_service),
) -> TaskResponse:
    """Approve or reject the proposed changes for a task that's paused
    awaiting approval. Approving resumes the graph through code
    modification, running the tests, and (on failure) the bounded
    diagnose-and-fix retry loop, ending in a final response. Rejecting
    resumes straight to a final response with nothing written to disk.

    This same endpoint resumes a DB-tracked execution too (Phase 7's
    conversation-message flow, see app/api/routes/conversations.py) —
    `thread_id` there is the execution's own id, and AgentService updates
    the execution row's status as part of resuming, transparently to this
    route.
    """
    try:
        result = await agent_service.submit_decision(thread_id, request.approved)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskNotAwaitingApprovalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AgentServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return TaskResponse(**result)
