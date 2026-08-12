from app.graph.graph import build_graph
from app.graph.state import GraphState


class AgentServiceError(Exception):
    """Raised when the LangGraph workflow fails to produce a response."""


class AgentService:
    """Builds and invokes the compiled LangGraph workflow — keeps graph
    execution details (initial state shape, error translation) out of the
    routes.
    """

    def __init__(self) -> None:
        self._graph = build_graph()

    def get_chat_response(self, message: str) -> str:
        initial_state: GraphState = {
            "user_request": message,
            "plan": "",
            "messages": [],
            "analysis": "",
            "final_response": "",
        }

        try:
            result = self._graph.invoke(initial_state)
        except Exception as exc:
            raise AgentServiceError(f"Agent workflow failed: {exc}") from exc

        final_response = result.get("final_response")
        if not final_response:
            raise AgentServiceError("Agent workflow produced no final response")

        return final_response


def get_agent_service() -> AgentService:
    """FastAPI dependency factory for AgentService."""
    return AgentService()
