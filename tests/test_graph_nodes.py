from langchain_core.messages import AIMessage

from app.core.config import get_settings
from app.graph.nodes import route_after_agent, tool_node


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


def test_tool_node_executes_requested_tool(tmp_path, monkeypatch) -> None:
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

    result = tool_node(state)

    get_settings.cache_clear()

    assert len(result["messages"]) == 1
    tool_message = result["messages"][0]
    assert tool_message.tool_call_id == "call_1"
    assert "app.py" in tool_message.content


def test_tool_node_handles_multiple_tool_calls_in_one_pass(tmp_path, monkeypatch) -> None:
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

    result = tool_node(state)

    get_settings.cache_clear()

    assert len(result["messages"]) == 2
    assert result["messages"][0].tool_call_id == "call_1"
    assert result["messages"][1].tool_call_id == "call_2"
    assert "def login" in result["messages"][1].content


def test_tool_node_reports_error_for_unknown_tool() -> None:
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "delete_everything", "args": {}, "id": "call_2"}],
            )
        ]
    }

    result = tool_node(state)

    assert "Error" in result["messages"][0].content
    assert result["messages"][0].tool_call_id == "call_2"
