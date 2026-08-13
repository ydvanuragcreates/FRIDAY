import uuid
from functools import lru_cache
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from app.graph.graph import build_graph
from app.graph.state import GraphState
from app.services.execution_recorder import record_assistant_message, update_execution_status


class AgentServiceError(Exception):
    """Raised when the LangGraph workflow fails to produce a response."""


class TaskNotFoundError(Exception):
    """Raised when a thread_id doesn't correspond to a known task."""


class TaskNotAwaitingApprovalError(Exception):
    """Raised when a decision is submitted for a task that isn't currently
    paused at the human-approval step (already decided, or not that far
    along yet).
    """


def _initial_state(
    message: str,
    *,
    project_id: str | None = None,
    conversation_id: str | None = None,
    execution_id: str | None = None,
) -> GraphState:
    return {
        "project_id": project_id,
        "conversation_id": conversation_id,
        "execution_id": execution_id,
        "user_request": message,
        "plan": "",
        "messages": [],
        "analysis": "",
        "files_inspected": [],
        "proposed_changes": [],
        "approved": None,
        "applied_changes": [],
        "test_results": "",
        "test_passed": False,
        "errors": [],
        "retry_count": 0,
        "final_response": "",
    }


class AgentService:
    """Builds and drives the compiled LangGraph workflow, including the
    human-in-the-loop pause/resume around code modification.

    A task spans *two* separate HTTP requests — one that runs the graph up
    to the approval interrupt, and one (arriving whenever the human gets
    around to it) that supplies the decision and resumes it. What survives
    between those two requests is the checkpointer's state for that
    thread_id, so this service — and its checkpointer — must be a single
    instance shared across requests (see `get_agent_service`, cached)
    rather than rebuilt per-request the way Phase 4 did, or the paused
    state would be lost as soon as the first request returned.

    Phase 7: `project_id`/`conversation_id`/`execution_id` are optional —
    the plain /api/chat and /api/tasks callers (Phases 4/5) omit them, so
    every DB-persistence call this class makes (all funneled through
    execution_recorder.update_execution_status) is skipped and those
    endpoints behave exactly as before. When `execution_id` IS given, it
    doubles as the LangGraph checkpointer's thread_id — the same run is
    both "the paused task with this thread_id" and "the execution row
    with this id," never two things that could drift out of sync.
    """

    def __init__(self) -> None:
        self._checkpointer = MemorySaver()
        self._graph = build_graph(checkpointer=self._checkpointer)

    def _config(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    async def _mark_failed(self, execution_id: str | None, error: Exception) -> None:
        if not execution_id:
            return
        try:
            await update_execution_status(execution_id, "failed", error_message=str(error), completed=True)
        except Exception:
            pass  # best-effort — a secondary DB failure here must not mask the original error being raised

    async def _sync_execution_status(self, execution_id: str, result: dict[str, Any]) -> None:
        """Translate the graph's own status vocabulary ('awaiting_approval'
        / 'completed') into executions.status and persist it. Note
        'completed' here means the graph finished running, independent of
        whether tests passed or changes were rejected — those outcomes
        are already captured in test_results/code_changes/errors.
        'failed' (see _mark_failed) is reserved for the graph itself
        raising, i.e. actual infrastructure/tool-crash failures.
        """
        if result["status"] == "awaiting_approval":
            await update_execution_status(execution_id, "waiting_for_approval")
        else:
            await update_execution_status(
                execution_id, "completed", completed=True, retry_count=result.get("retry_count", 0)
            )

    async def start_task(
        self,
        message: str,
        *,
        project_id: str | None = None,
        conversation_id: str | None = None,
        execution_id: str | None = None,
    ) -> dict:
        """Run the graph for a new task up to either completion or the
        human-approval interrupt, whichever comes first.
        """
        thread_id = execution_id or str(uuid.uuid4())
        initial_state = _initial_state(
            message, project_id=project_id, conversation_id=conversation_id, execution_id=execution_id
        )

        try:
            if execution_id:
                await update_execution_status(execution_id, "running")
            await self._graph.ainvoke(initial_state, self._config(thread_id))
        except Exception as exc:
            await self._mark_failed(execution_id, exc)
            raise AgentServiceError(f"Agent workflow failed: {exc}") from exc

        result = await self._task_status(thread_id)
        if execution_id:
            await self._sync_execution_status(execution_id, result)
        return result

    async def submit_decision(self, thread_id: str, approved: bool) -> dict:
        """Record the human's approve/reject decision for a paused task and
        resume the graph — into apply_changes and, if approved, on through
        testing (and the fix-and-retest loop) to a final response.
        """
        config = self._config(thread_id)
        snapshot = await self._graph.aget_state(config)
        if not snapshot.values:
            raise TaskNotFoundError(f"No task found for thread_id '{thread_id}'")
        if "apply_changes" not in snapshot.next:
            raise TaskNotAwaitingApprovalError(
                f"Task '{thread_id}' is not currently awaiting approval"
            )

        execution_id = snapshot.values.get("execution_id")
        conversation_id = snapshot.values.get("conversation_id")

        await self._graph.aupdate_state(config, {"approved": approved})
        try:
            if execution_id:
                await update_execution_status(execution_id, "running")
            await self._graph.ainvoke(None, config)
        except Exception as exc:
            await self._mark_failed(execution_id, exc)
            raise AgentServiceError(f"Agent workflow failed: {exc}") from exc

        result = await self._task_status(thread_id)
        if execution_id:
            await self._sync_execution_status(execution_id, result)
            # start_task's completion path has ConversationService save the
            # assistant message itself; submit_decision has no such caller
            # above it (it's reached directly via the Phase 5 approval
            # endpoint), so it has to save the reply itself here instead.
            if conversation_id and result["status"] == "completed" and result.get("final_response"):
                await record_assistant_message(conversation_id, result["final_response"])
        return result

    async def get_task_status(self, thread_id: str) -> dict:
        snapshot = await self._graph.aget_state(self._config(thread_id))
        if not snapshot.values:
            raise TaskNotFoundError(f"No task found for thread_id '{thread_id}'")
        return await self._task_status(thread_id)

    async def _task_status(self, thread_id: str) -> dict[str, Any]:
        snapshot = await self._graph.aget_state(self._config(thread_id))
        values = snapshot.values
        awaiting_approval = "apply_changes" in snapshot.next
        return {
            "thread_id": thread_id,
            "status": "awaiting_approval" if awaiting_approval else "completed",
            "plan": values.get("plan", ""),
            "analysis": values.get("analysis", ""),
            "files_inspected": values.get("files_inspected", []),
            "proposed_changes": values.get("proposed_changes", []),
            "applied_changes": values.get("applied_changes", []),
            "test_results": values.get("test_results", ""),
            "test_passed": values.get("test_passed", False),
            "retry_count": values.get("retry_count", 0),
            "errors": values.get("errors", []),
            "final_response": values.get("final_response", ""),
        }

    async def get_chat_response(self, message: str) -> str:
        """Backwards-compatible, single-shot entry point for /api/chat: for
        pure Q&A requests that need no code change, the graph runs straight
        through to a final response. A request that DOES propose changes
        will pause for approval instead — since /api/chat is synchronous
        and has no approval step of its own, that's surfaced as an error
        pointing at the task-based endpoints (the thread itself is not
        wasted; it can still be approved/rejected via those endpoints).
        """
        result = await self.start_task(message)
        if result["status"] == "awaiting_approval":
            raise AgentServiceError(
                "This request proposes code changes, which need human approval "
                f"before they're applied. Continue via POST /api/tasks/"
                f"{result['thread_id']}/decision instead of /api/chat."
            )

        final_response = result.get("final_response")
        if not final_response:
            raise AgentServiceError("Agent workflow produced no final response")
        return final_response


@lru_cache
def get_agent_service() -> AgentService:
    """Process-wide singleton so the in-memory checkpointer survives across
    the separate start/decision requests that make up one task.
    """
    return AgentService()
