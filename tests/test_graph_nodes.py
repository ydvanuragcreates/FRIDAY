from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable

import app.graph.nodes as nodes_module
from app.core.config import get_settings
from app.graph.nodes import (
    apply_changes_node,
    code_fix_node,
    implementer_node,
    route_after_agent,
    route_after_apply,
    route_after_implementer,
    route_after_tests,
    run_tests_node,
    tool_node,
)


class FakeChatModel(Runnable):
    """A minimal Runnable stand-in for ChatAnthropic: composes with `|`
    like a real chat model, and `.bind_tools(...)` just returns itself so
    the same canned response comes back regardless of which tools were
    bound. Lets node tests exercise real prompt/chain wiring without
    hitting the network. Nodes are async (Phase 7) and call `.ainvoke()`,
    not `.invoke()`.
    """

    def __init__(self, response):
        self._response = response

    def invoke(self, input, config=None, **kwargs):
        raise NotImplementedError("nodes call ainvoke, not invoke")

    async def ainvoke(self, input, config=None, **kwargs):
        return self._response

    def bind_tools(self, tools):
        return self


def test_route_after_agent_goes_to_tools_when_tool_calls_present() -> None:
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "list_files", "args": {"directory": "."}, "id": "call_1"}
                ],
            )
        ]
    }

    assert route_after_agent(state) == "tools"


def test_route_after_agent_goes_to_analyzer_when_no_tool_calls() -> None:
    state = {"messages": [AIMessage(content="I found what I needed.")]}

    assert route_after_agent(state) == "analyzer"


async def test_tool_node_executes_requested_tool(tmp_path, monkeypatch) -> None:
    (tmp_path / "app.py").write_text("print('hi')\n")
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "list_files", "args": {"directory": "."}, "id": "call_1"}
                ],
            )
        ]
    }

    result = await tool_node(state)

    get_settings.cache_clear()

    assert len(result["messages"]) == 1
    tool_message = result["messages"][0]
    assert tool_message.tool_call_id == "call_1"
    assert "app.py" in tool_message.content


async def test_tool_node_handles_multiple_tool_calls_in_one_pass(tmp_path, monkeypatch) -> None:
    (tmp_path / "auth.py").write_text("def login():\n    pass\n")
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "list_files", "args": {"directory": "."}, "id": "call_1"},
                    {
                        "name": "read_file",
                        "args": {"file_path": "auth.py"},
                        "id": "call_2",
                    },
                ],
            )
        ]
    }

    result = await tool_node(state)

    get_settings.cache_clear()

    assert len(result["messages"]) == 2
    assert result["messages"][0].tool_call_id == "call_1"
    assert result["messages"][1].tool_call_id == "call_2"
    assert "def login" in result["messages"][1].content


async def test_tool_node_reports_error_for_unknown_tool() -> None:
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "delete_everything", "args": {}, "id": "call_2"}],
            )
        ]
    }

    result = await tool_node(state)

    assert "Error" in result["messages"][0].content
    assert result["messages"][0].tool_call_id == "call_2"


def test_route_after_implementer_with_no_proposed_changes_goes_to_responder() -> None:
    assert route_after_implementer({"proposed_changes": []}) == "responder"


def test_route_after_implementer_with_proposed_changes_goes_to_apply_changes() -> None:
    state = {
        "proposed_changes": [
            {"file_path": "a.py", "action": "create", "content": "x = 1\n", "diff": "..."}
        ]
    }
    assert route_after_implementer(state) == "apply_changes"


async def test_implementer_node_diffs_proposed_tool_calls(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    fake_response = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "create_file",
                "args": {"file_path": "new.py", "content": "x = 1\n"},
                "id": "call_1",
            }
        ],
    )
    monkeypatch.setattr(nodes_module, "get_chat_model", lambda: FakeChatModel(fake_response))

    result = await implementer_node(
        {"user_request": "add a module", "plan": "1. add it", "analysis": "no existing file"}
    )

    get_settings.cache_clear()

    assert result["approved"] is None
    assert len(result["proposed_changes"]) == 1
    change = result["proposed_changes"][0]
    assert change["file_path"] == "new.py"
    assert change["action"] == "create"
    assert "+x = 1" in change["diff"]


async def test_implementer_node_no_tool_calls_yields_no_proposed_changes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    fake_response = AIMessage(content="No change needed.", tool_calls=[])
    monkeypatch.setattr(nodes_module, "get_chat_model", lambda: FakeChatModel(fake_response))

    result = await implementer_node({"user_request": "explain X", "plan": "1. explain", "analysis": ""})

    get_settings.cache_clear()

    assert result["proposed_changes"] == []


async def test_apply_changes_node_writes_files_when_approved(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    state = {
        "approved": True,
        "proposed_changes": [
            {"file_path": "new.py", "action": "create", "content": "x = 1\n", "diff": "..."}
        ],
        "errors": [],
    }
    result = await apply_changes_node(state)

    get_settings.cache_clear()

    assert result["applied_changes"] == ["new.py"]
    assert (tmp_path / "new.py").read_text() == "x = 1\n"
    assert result["errors"] == []


async def test_apply_changes_node_skips_writes_when_not_approved(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    state = {
        "approved": False,
        "proposed_changes": [
            {"file_path": "new.py", "action": "create", "content": "x = 1\n", "diff": "..."}
        ],
        "errors": [],
    }
    result = await apply_changes_node(state)

    get_settings.cache_clear()

    assert result["applied_changes"] == []
    assert not (tmp_path / "new.py").exists()
    assert any("not approved" in err for err in result["errors"])


def test_route_after_apply_goes_to_run_tests_when_approved() -> None:
    assert route_after_apply({"approved": True}) == "run_tests"


def test_route_after_apply_goes_to_responder_when_not_approved() -> None:
    assert route_after_apply({"approved": False}) == "responder"


async def test_run_tests_node_reports_pass(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("TEST_COMMAND", "python --version")
    get_settings.cache_clear()

    result = await run_tests_node({})

    get_settings.cache_clear()

    assert result["test_passed"] is True
    assert result["test_results"].startswith("Exit code: 0")


async def test_run_tests_node_reports_failure(monkeypatch, tmp_path) -> None:
    (tmp_path / "test_fails.py").write_text("def test_fail():\n    assert False\n")
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("TEST_COMMAND", "pytest")
    get_settings.cache_clear()

    result = await run_tests_node({})

    get_settings.cache_clear()

    assert result["test_passed"] is False
    assert not result["test_results"].startswith("Exit code: 0")


def test_route_after_tests_goes_to_responder_when_passed() -> None:
    assert route_after_tests({"test_passed": True, "retry_count": 0}) == "responder"


def test_route_after_tests_goes_to_error_analysis_when_retries_remain() -> None:
    assert route_after_tests({"test_passed": False, "retry_count": 0}) == "error_analysis"


def test_route_after_tests_gives_up_when_retries_exhausted(monkeypatch) -> None:
    monkeypatch.setenv("MAX_RETRIES", "2")
    get_settings.cache_clear()

    result = route_after_tests({"test_passed": False, "retry_count": 2})

    get_settings.cache_clear()

    assert result == "responder"


async def test_code_fix_node_applies_fix_and_accumulates_applied_changes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    state = {
        "applied_changes": ["already_applied.py"],
        "errors": [],
        "proposed_changes": [
            {"file_path": "fix.py", "action": "create", "content": "y = 2\n", "diff": "..."}
        ],
    }
    result = await code_fix_node(state)

    get_settings.cache_clear()

    assert result["applied_changes"] == ["already_applied.py", "fix.py"]
    assert (tmp_path / "fix.py").read_text() == "y = 2\n"
