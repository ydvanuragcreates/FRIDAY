from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.agent_service import (
    AgentService,
    AgentServiceError,
    TaskNotAwaitingApprovalError,
    TaskNotFoundError,
)


@pytest.fixture
def agent_service() -> AgentService:
    """A real AgentService with its compiled graph swapped for a mock —
    building the graph doesn't touch the LLM (nodes only construct their
    chat model when actually invoked), so no API key or network call is
    needed to test the service's own logic. The graph's own methods are
    async (Phase 7: `.ainvoke`/`.aget_state`/`.aupdate_state`), so they're
    mocked with AsyncMock rather than plain MagicMock.
    """
    service = AgentService()
    service._graph = MagicMock()
    service._graph.ainvoke = AsyncMock()
    service._graph.aget_state = AsyncMock()
    service._graph.aupdate_state = AsyncMock()
    return service


def _snapshot(values: dict, next_nodes: tuple = ()) -> MagicMock:
    snapshot = MagicMock()
    snapshot.values = values
    snapshot.next = next_nodes
    return snapshot


async def test_start_task_returns_completed_status_when_no_approval_needed(
    agent_service: AgentService,
) -> None:
    agent_service._graph.aget_state.return_value = _snapshot(
        {"final_response": "Hello there!", "plan": "1. Greet"}, next_nodes=()
    )

    result = await agent_service.start_task("Hi")

    assert result["status"] == "completed"
    assert result["final_response"] == "Hello there!"
    assert "thread_id" in result
    agent_service._graph.ainvoke.assert_called_once()


async def test_start_task_returns_awaiting_approval_status_when_paused(
    agent_service: AgentService,
) -> None:
    agent_service._graph.aget_state.return_value = _snapshot(
        {"plan": "1. Add a file", "proposed_changes": [{"file_path": "a.py"}]},
        next_nodes=("apply_changes",),
    )

    result = await agent_service.start_task("Add a file")

    assert result["status"] == "awaiting_approval"
    assert result["proposed_changes"] == [{"file_path": "a.py"}]


async def test_start_task_wraps_graph_errors(agent_service: AgentService) -> None:
    agent_service._graph.ainvoke.side_effect = RuntimeError("graph failed")

    with pytest.raises(AgentServiceError, match="graph failed"):
        await agent_service.start_task("Hi")


async def test_submit_decision_resumes_a_paused_task(agent_service: AgentService) -> None:
    agent_service._graph.aget_state.side_effect = [
        _snapshot({"plan": "1. Add a file"}, next_nodes=("apply_changes",)),
        _snapshot({"final_response": "Done.", "applied_changes": ["a.py"]}, next_nodes=()),
    ]

    result = await agent_service.submit_decision("thread-1", approved=True)

    agent_service._graph.aupdate_state.assert_called_once_with(
        {"configurable": {"thread_id": "thread-1"}}, {"approved": True}
    )
    agent_service._graph.ainvoke.assert_called_once_with(
        None, {"configurable": {"thread_id": "thread-1"}}
    )
    assert result["status"] == "completed"
    assert result["final_response"] == "Done."


async def test_submit_decision_raises_for_unknown_thread(agent_service: AgentService) -> None:
    agent_service._graph.aget_state.return_value = _snapshot({}, next_nodes=())

    with pytest.raises(TaskNotFoundError):
        await agent_service.submit_decision("nonexistent", approved=True)


async def test_submit_decision_raises_when_not_awaiting_approval(agent_service: AgentService) -> None:
    agent_service._graph.aget_state.return_value = _snapshot(
        {"final_response": "Already done."}, next_nodes=()
    )

    with pytest.raises(TaskNotAwaitingApprovalError):
        await agent_service.submit_decision("thread-1", approved=True)


async def test_get_task_status_raises_for_unknown_thread(agent_service: AgentService) -> None:
    agent_service._graph.aget_state.return_value = _snapshot({}, next_nodes=())

    with pytest.raises(TaskNotFoundError):
        await agent_service.get_task_status("nonexistent")


async def test_get_chat_response_returns_final_response_for_completed_task(
    agent_service: AgentService,
) -> None:
    agent_service._graph.aget_state.return_value = _snapshot(
        {"final_response": "Hello there!"}, next_nodes=()
    )

    result = await agent_service.get_chat_response("Hi")

    assert result == "Hello there!"


async def test_get_chat_response_raises_when_task_needs_approval(agent_service: AgentService) -> None:
    agent_service._graph.aget_state.return_value = _snapshot(
        {"proposed_changes": [{"file_path": "a.py"}]}, next_nodes=("apply_changes",)
    )

    with pytest.raises(AgentServiceError, match="/api/tasks/"):
        await agent_service.get_chat_response("Add a file")


async def test_get_chat_response_raises_on_empty_final_response(agent_service: AgentService) -> None:
    agent_service._graph.aget_state.return_value = _snapshot({"final_response": ""}, next_nodes=())

    with pytest.raises(AgentServiceError, match="no final response"):
        await agent_service.get_chat_response("Hi")
