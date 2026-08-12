from unittest.mock import MagicMock

import pytest

from app.services.agent_service import AgentService, AgentServiceError


@pytest.fixture
def agent_service() -> AgentService:
    """A real AgentService with its compiled graph swapped for a mock —
    building the graph doesn't touch the LLM (nodes only construct their
    chat model when actually invoked), so no API key or network call is
    needed to test the service's own logic.
    """
    service = AgentService()
    service._graph = MagicMock()
    return service


def test_get_chat_response_returns_final_response(agent_service: AgentService) -> None:
    agent_service._graph.invoke.return_value = {
        "user_request": "Hi",
        "plan": "1. Greet the user",
        "analysis": "No risks",
        "final_response": "Hello there!",
    }

    result = agent_service.get_chat_response("Hi")

    assert result == "Hello there!"


def test_get_chat_response_seeds_initial_state(agent_service: AgentService) -> None:
    agent_service._graph.invoke.return_value = {"final_response": "ok"}

    agent_service.get_chat_response("Build a login form")

    agent_service._graph.invoke.assert_called_once_with(
        {
            "user_request": "Build a login form",
            "plan": "",
            "messages": [],
            "analysis": "",
            "final_response": "",
        }
    )


def test_get_chat_response_wraps_graph_errors(agent_service: AgentService) -> None:
    agent_service._graph.invoke.side_effect = RuntimeError("graph failed")

    with pytest.raises(AgentServiceError, match="graph failed"):
        agent_service.get_chat_response("Hi")


def test_get_chat_response_raises_on_empty_final_response(
    agent_service: AgentService,
) -> None:
    agent_service._graph.invoke.return_value = {"final_response": ""}

    with pytest.raises(AgentServiceError, match="no final response"):
        agent_service.get_chat_response("Hi")
