import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable

import app.graph.nodes as nodes_module
from app.core.config import get_settings


class FakeChatModel(Runnable):
    """Queue of canned AIMessage responses, consumed one per `.ainvoke()`
    call — see app/graph/nodes.py, every LLM-calling node now awaits
    `.ainvoke()` rather than `.invoke()` (Phase 7's async conversion).
    """

    def __init__(self, responses):
        self._responses = iter(responses)

    def invoke(self, input, config=None, **kwargs):
        raise NotImplementedError("this fake only supports ainvoke")

    async def ainvoke(self, input, config=None, **kwargs):
        return next(self._responses)

    def bind_tools(self, tools):
        return self


def _qa_only_responses(final_answer: str) -> list[AIMessage]:
    """planner, agent (no tool calls), analyzer, implementer (no proposed
    changes), responder — the shortest path through the graph, ending
    with no approval/apply/test phase at all.
    """
    return [
        AIMessage(content="1. answer the question"),
        AIMessage(content="nothing to look up", tool_calls=[]),
        AIMessage(content="looks fine"),
        AIMessage(content="", tool_calls=[]),
        AIMessage(content=final_answer),
    ]


@pytest.fixture(autouse=True)
def _isolated_workspace(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _create_project_and_conversation(client) -> tuple[str, str]:
    project = client.post(
        "/api/projects", json={"name": "Demo", "repository_path": "/workspace/demo"}
    ).json()
    conversation = client.post(
        f"/api/projects/{project['id']}/conversations", json={"title": "Chat"}
    ).json()
    return project["id"], conversation["id"]


def test_create_conversation_requires_existing_project(client) -> None:
    response = client.post(
        "/api/projects/00000000-0000-0000-0000-000000000099/conversations", json={"title": "x"}
    )
    assert response.status_code == 404


def test_create_and_list_conversations(client) -> None:
    project_id, conversation_id = _create_project_and_conversation(client)

    response = client.get(f"/api/projects/{project_id}/conversations")

    assert response.status_code == 200
    assert [c["id"] for c in response.json()] == [conversation_id]


def test_get_conversation_returns_404_for_unknown_id(client) -> None:
    response = client.get("/api/conversations/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404


def test_send_message_runs_graph_and_saves_both_messages(client, monkeypatch: pytest.MonkeyPatch) -> None:
    _, conversation_id = _create_project_and_conversation(client)
    # One shared FakeChatModel instance — get_chat_model() is called once
    # per node (planner, agent, analyzer, implementer, responder), and
    # they all need to draw from the SAME response queue in order.
    # Constructing a new FakeChatModel per call (e.g. inside the lambda)
    # would reset the queue every time and every node would see response #1.
    fake_model = FakeChatModel(_qa_only_responses("The answer is 42."))
    monkeypatch.setattr(nodes_module, "get_chat_model", lambda: fake_model)

    response = client.post(
        f"/api/conversations/{conversation_id}/messages", json={"content": "What is the answer?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["user_message"]["content"] == "What is the answer?"
    assert body["assistant_message"]["content"] == "The answer is 42."

    messages = client.get(f"/api/conversations/{conversation_id}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_send_message_returns_404_for_unknown_conversation(client) -> None:
    response = client.post(
        "/api/conversations/00000000-0000-0000-0000-000000000099/messages", json={"content": "hi"}
    )
    assert response.status_code == 404


def test_send_message_creates_an_execution_visible_in_history(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, conversation_id = _create_project_and_conversation(client)
    fake_model = FakeChatModel(_qa_only_responses("Done."))
    monkeypatch.setattr(nodes_module, "get_chat_model", lambda: fake_model)

    send_result = client.post(
        f"/api/conversations/{conversation_id}/messages", json={"content": "hello"}
    ).json()
    execution_id = send_result["execution_id"]

    history = client.get(f"/api/projects/{project_id}/executions").json()
    assert [e["id"] for e in history] == [execution_id]

    detail = client.get(f"/api/executions/{execution_id}").json()
    assert detail["status"] == "completed"
    assert len(detail["agent_plans"]) == 1
