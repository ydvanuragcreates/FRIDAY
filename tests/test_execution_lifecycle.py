"""End-to-end coverage of the thing Phase 7 is really about: a
conversation message that needs a code change pauses for human approval,
and every stage — plan, tool calls, code change, test result, final
status — lands in the database as the graph actually runs, not just once
at the end. See README > "How LangGraph talks to the database".
"""

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable

import app.graph.nodes as nodes_module
from app.core.config import get_settings


class FakeChatModel(Runnable):
    def __init__(self, responses):
        self._responses = iter(responses)

    def invoke(self, input, config=None, **kwargs):
        raise NotImplementedError

    async def ainvoke(self, input, config=None, **kwargs):
        return next(self._responses)

    def bind_tools(self, tools):
        return self


def _code_change_responses(file_path: str, content: str, final_answer: str) -> list[AIMessage]:
    return [
        AIMessage(content="1. add the file"),  # planner
        AIMessage(content="nothing to look up", tool_calls=[]),  # agent -> analyzer
        AIMessage(content="ready to implement"),  # analyzer
        AIMessage(  # implementer proposes a change
            content="",
            tool_calls=[
                {"name": "create_file", "args": {"file_path": file_path, "content": content}, "id": "call_1"}
            ],
        ),
        AIMessage(content=final_answer),  # responder, after approval + tests
    ]


@pytest.fixture(autouse=True)
def _isolated_workspace(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("TEST_COMMAND", "python --version")  # always exits 0, no retry loop needed
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def _create_project_and_conversation(client, repository_path: str) -> tuple[str, str]:
    project = client.post(
        "/api/projects", json={"name": "Demo", "repository_path": repository_path}
    ).json()
    conversation = client.post(
        f"/api/projects/{project['id']}/conversations", json={"title": "Chat"}
    ).json()
    return project["id"], conversation["id"]


def test_code_change_pauses_for_approval_and_persists_plan(
    client, monkeypatch: pytest.MonkeyPatch, _isolated_workspace
) -> None:
    project_id, conversation_id = _create_project_and_conversation(client, str(_isolated_workspace))
    # One shared instance — see test_api_conversations.py for why the
    # lambda must not construct a fresh FakeChatModel per node call.
    fake_model = FakeChatModel(_code_change_responses("hello.py", "print('hi')\n", "Done!"))
    monkeypatch.setattr(nodes_module, "get_chat_model", lambda: fake_model)

    response = client.post(
        f"/api/conversations/{conversation_id}/messages", json={"content": "add hello.py"}
    )

    assert response.status_code == 200
    body = response.json()
    # SendMessageResponse.status mirrors AgentService's own vocabulary
    # ("awaiting_approval") — the DB record separately uses
    # ExecutionStatus.WAITING_FOR_APPROVAL, asserted below.
    assert body["status"] == "awaiting_approval"
    assert body["assistant_message"] is None
    execution_id = body["execution_id"]

    detail = client.get(f"/api/executions/{execution_id}").json()
    assert detail["status"] == "waiting_for_approval"
    assert len(detail["agent_plans"]) == 1
    assert detail["code_changes"] == []  # not written yet — see apply_changes_node

    # nothing written to disk yet either
    assert not (_isolated_workspace / "hello.py").exists()


def test_approving_resumes_writes_file_and_completes(
    client, monkeypatch: pytest.MonkeyPatch, _isolated_workspace
) -> None:
    project_id, conversation_id = _create_project_and_conversation(client, str(_isolated_workspace))
    fake_model = FakeChatModel(_code_change_responses("hello.py", "print('hi')\n", "Done!"))
    monkeypatch.setattr(nodes_module, "get_chat_model", lambda: fake_model)

    send_result = client.post(
        f"/api/conversations/{conversation_id}/messages", json={"content": "add hello.py"}
    ).json()
    execution_id = send_result["execution_id"]

    decision_response = client.post(f"/api/tasks/{execution_id}/decision", json={"approved": True})

    assert decision_response.status_code == 200
    decision_body = decision_response.json()
    assert decision_body["status"] == "completed"
    assert decision_body["final_response"] == "Done!"
    assert (_isolated_workspace / "hello.py").read_text() == "print('hi')\n"

    detail = client.get(f"/api/executions/{execution_id}").json()
    assert detail["status"] == "completed"
    assert len(detail["code_changes"]) == 1
    assert detail["code_changes"][0]["approved"] is True
    assert detail["code_changes"][0]["applied"] is True
    assert len(detail["test_results"]) == 1
    assert detail["test_results"][0]["passed"] is True

    # the conversation should now show both messages, including the
    # reply that was only available after resuming (see
    # execution_recorder.record_assistant_message)
    messages = client.get(f"/api/conversations/{conversation_id}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "Done!"


def test_rejecting_skips_apply_and_completes_without_writing(
    client, monkeypatch: pytest.MonkeyPatch, _isolated_workspace
) -> None:
    project_id, conversation_id = _create_project_and_conversation(client, str(_isolated_workspace))
    fake_model = FakeChatModel(
        _code_change_responses("hello.py", "print('hi')\n", "Rejected as requested.")
    )
    monkeypatch.setattr(nodes_module, "get_chat_model", lambda: fake_model)

    send_result = client.post(
        f"/api/conversations/{conversation_id}/messages", json={"content": "add hello.py"}
    ).json()
    execution_id = send_result["execution_id"]

    decision_response = client.post(f"/api/tasks/{execution_id}/decision", json={"approved": False})

    assert decision_response.status_code == 200
    decision_body = decision_response.json()
    assert decision_body["status"] == "completed"
    assert not (_isolated_workspace / "hello.py").exists()

    detail = client.get(f"/api/executions/{execution_id}").json()
    assert detail["code_changes"][0]["approved"] is False
    assert detail["code_changes"][0]["applied"] is False
    assert detail["test_results"] == []  # route_after_apply skips testing when rejected


def test_decision_on_unknown_execution_returns_404(client) -> None:
    response = client.post(
        "/api/tasks/00000000-0000-0000-0000-000000000099/decision", json={"approved": True}
    )
    assert response.status_code == 404


class _RaisingChatModel(Runnable):
    """Simulates an LLM/infrastructure failure partway through a run —
    e.g. an Anthropic API error — for exercising the "execution failed"
    path (see README > "Error handling" / §15 in the spec: status must
    become 'failed' with error_message set, never silently swallowed).
    """

    def invoke(self, input, config=None, **kwargs):
        raise NotImplementedError

    async def ainvoke(self, input, config=None, **kwargs):
        raise RuntimeError("simulated Anthropic API failure")

    def bind_tools(self, tools):
        return self


def test_graph_failure_marks_execution_failed_with_error_message(
    client, monkeypatch: pytest.MonkeyPatch, _isolated_workspace
) -> None:
    project_id, conversation_id = _create_project_and_conversation(client, str(_isolated_workspace))
    monkeypatch.setattr(nodes_module, "get_chat_model", lambda: _RaisingChatModel())

    response = client.post(
        f"/api/conversations/{conversation_id}/messages", json={"content": "add hello.py"}
    )

    assert response.status_code == 502

    # the execution row must reflect the failure — not be left "running"
    # or silently dropped
    history = client.get(f"/api/projects/{project_id}/executions").json()
    assert len(history) == 1
    execution_id = history[0]["id"]
    detail = client.get(f"/api/executions/{execution_id}").json()
    assert detail["status"] == "failed"
    assert "simulated Anthropic API failure" in detail["error_message"]
    assert detail["completed_at"] is not None
