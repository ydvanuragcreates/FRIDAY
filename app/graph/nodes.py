from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser

from app.core.config import get_settings
from app.core.diff import unified_file_diff
from app.core.llm import get_chat_model
from app.core.workspace import WorkspacePathError, resolve_workspace_path
from app.graph.state import GraphState, ProposedChange
from app.prompts.agent_prompts import (
    AGENT_SYSTEM_PROMPT,
    ANALYZER_PROMPT,
    ERROR_ANALYSIS_PROMPT,
    IMPLEMENTER_SYSTEM_PROMPT,
    PLANNER_PROMPT,
    RESPONDER_PROMPT,
)
from app.services.execution_recorder import record_code_change, record_plan, record_test_result, record_tool_call
from app.tools import ALL_TOOLS, INVESTIGATION_TOOLS, WRITE_TOOLS

TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}
WRITE_TOOL_NAMES = {t.name for t in WRITE_TOOLS}

# Every node below is `async def`, calling `.ainvoke()` instead of
# `.invoke()`, even nodes with nothing to persist (agent_node,
# analyzer_node, responder_node). Two reasons, not one: (1) whichever
# nodes DO persist (planner, tools, apply_changes, run_tests, ...) need
# to `await` a DB call, which requires the node itself to be a coroutine;
# (2) once this graph runs inside an async FastAPI app with a real
# asyncpg connection pool, a synchronous node blocking for the length of
# an LLM call would stall the event loop for every other concurrent
# request, DB-bound or not. Converting everything uniformly avoids ending
# up with a confusing mix of "some nodes block, some don't." Tool
# implementations themselves (app/tools/*.py) are untouched — LangChain's
# `BaseTool.ainvoke()` runs a sync tool function in a thread automatically.


async def planner_node(state: GraphState) -> dict:
    """Turn the raw user request into a short, concrete plan."""
    chain = PLANNER_PROMPT | get_chat_model() | StrOutputParser()
    plan = await chain.ainvoke({"user_request": state["user_request"]})

    if state.get("execution_id"):
        await record_plan(state["execution_id"], plan)

    return {"plan": plan}


async def agent_node(state: GraphState) -> dict:
    """Decide whether another tool call is needed to gather information, or
    whether enough has been gathered already.

    Runs in a loop with `tool_node` (see graph.py's conditional edge): each
    pass either ends in another round of tool requests or in a plain-text
    summary of findings with no tool calls, which ends the loop. Only
    bound to the read-only/non-destructive INVESTIGATION_TOOLS — it cannot
    modify the workspace.
    """
    llm_with_tools = get_chat_model().bind_tools(INVESTIGATION_TOOLS)

    if not state["messages"]:
        # First pass through the loop — seed the tool-calling conversation
        # from the user's request and the plan produced upstream.
        seed: list[BaseMessage] = [
            SystemMessage(content=AGENT_SYSTEM_PROMPT),
            HumanMessage(
                content=f"User request: {state['user_request']}\n\nPlan:\n{state['plan']}"
            ),
        ]
        response = await llm_with_tools.ainvoke(seed)
        return {"messages": [*seed, response]}

    # Later passes — the message history already holds the seed plus any
    # prior tool calls/results; just continue the conversation.
    response = await llm_with_tools.ainvoke(state["messages"])
    return {"messages": [response]}


async def tool_node(state: GraphState) -> dict:
    """Execute every tool call requested in the agent's last message and
    return the results as ToolMessages, each tagged with the matching
    tool_call_id so the model can correlate a result back to its request.

    Only reached during the repository-analysis loop (see graph.py), where
    the agent is bound to INVESTIGATION_TOOLS, so nothing executed here
    modifies the workspace. Every successful read_file call is recorded
    into `files_inspected` for the final response to cite, and every call
    is persisted as a tool_call row when this run has an execution_id.
    """
    last_message = state["messages"][-1]
    results: list[ToolMessage] = []
    files_inspected = list(state.get("files_inspected", []))
    execution_id = state.get("execution_id")

    for tool_call in last_message.tool_calls:
        tool_fn = TOOLS_BY_NAME.get(tool_call["name"])
        if tool_fn is None:
            content = f"Error: unknown tool '{tool_call['name']}'"
        else:
            try:
                content = await tool_fn.ainvoke(tool_call["args"])
            except Exception as exc:  # surface any tool failure to the model, don't crash the graph
                content = f"Error: tool '{tool_call['name']}' failed: {exc}"

        succeeded = not str(content).startswith("Error")

        if tool_call["name"] == "read_file" and succeeded:
            file_path = tool_call["args"].get("file_path")
            if file_path and file_path not in files_inspected:
                files_inspected.append(file_path)

        if execution_id:
            await record_tool_call(
                execution_id, tool_call["name"], tool_call["args"], str(content), success=succeeded
            )

        results.append(ToolMessage(content=str(content), tool_call_id=tool_call["id"]))

    return {"messages": results, "files_inspected": files_inspected}


def route_after_agent(state: GraphState) -> Literal["tools", "analyzer"]:
    """Conditional edge after `agent`: if it just requested tool calls,
    loop through tool execution and back to the agent; otherwise it's done
    gathering information, so move on to analysis.
    """
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "analyzer"


def _render_agent_transcript(messages: list[BaseMessage]) -> str:
    """Render the agent's tool calls and results (skipping the seed
    system/human framing messages) into plain text for the analyzer.
    """
    lines: list[str] = []
    for message in messages:
        if isinstance(message, AIMessage):
            for tool_call in message.tool_calls:
                lines.append(f"Called {tool_call['name']}({tool_call['args']})")
            if message.content:
                lines.append(f"Agent notes: {message.content}")
        elif isinstance(message, ToolMessage):
            lines.append(f"Result:\n{message.content}")
    return "\n\n".join(lines) if lines else "(no tool calls were made)"


async def analyzer_node(state: GraphState) -> dict:
    """Analyze the request, plan, and everything gathered via tool calls."""
    findings = _render_agent_transcript(state["messages"])
    chain = ANALYZER_PROMPT | get_chat_model() | StrOutputParser()
    analysis = await chain.ainvoke(
        {
            "user_request": state["user_request"],
            "plan": state["plan"],
            "findings": findings,
        }
    )
    return {"analysis": analysis}


async def _propose_changes(instruction: str) -> list[ProposedChange]:
    """Ask the LLM to propose file changes for `instruction` by calling
    create_file/write_file, then turn each requested tool call into a
    diffed proposal WITHOUT executing it — nothing here touches disk.
    Actually applying a proposal happens later, in apply_changes_node or
    code_fix_node, using the same underlying tool functions.
    """
    llm_with_tools = get_chat_model().bind_tools(WRITE_TOOLS)
    seed = [
        SystemMessage(content=IMPLEMENTER_SYSTEM_PROMPT),
        HumanMessage(content=instruction),
    ]
    response = await llm_with_tools.ainvoke(seed)

    proposals: list[ProposedChange] = []
    for tool_call in response.tool_calls:
        if tool_call["name"] not in WRITE_TOOL_NAMES:
            continue

        file_path = tool_call["args"].get("file_path", "")
        new_content = tool_call["args"].get("content", "")

        old_content = ""
        try:
            target = resolve_workspace_path(file_path)
            if target.exists() and target.is_file():
                old_content = target.read_text(encoding="utf-8", errors="replace")
        except (WorkspacePathError, OSError):
            old_content = ""

        action: Literal["create", "write"] = (
            "create" if tool_call["name"] == "create_file" else "write"
        )
        proposals.append(
            ProposedChange(
                file_path=file_path,
                action=action,
                content=new_content,
                diff=unified_file_diff(file_path, old_content, new_content),
            )
        )

    return proposals


async def implementer_node(state: GraphState) -> dict:
    """Turn the plan + repository analysis into a concrete, diffed set of
    proposed file changes for a human to review — this is the
    "Implementation plan" stage. Nothing is written to disk (or persisted
    to code_changes) yet — see apply_changes_node for why persistence
    waits until approval is known.
    """
    instruction = (
        f"User request: {state['user_request']}\n\n"
        f"Plan:\n{state['plan']}\n\n"
        f"Repository analysis:\n{state['analysis']}\n\n"
        "Propose the concrete file changes needed to fulfill the request."
    )
    return {"proposed_changes": await _propose_changes(instruction), "approved": None}


def route_after_implementer(state: GraphState) -> Literal["apply_changes", "responder"]:
    """If the implementer decided no code change is needed, skip approval,
    modification, and testing entirely and go straight to the final
    response. Otherwise proceed to apply_changes — which is where
    `interrupt_before` pauses the graph for human approval (see graph.py).
    """
    return "apply_changes" if state.get("proposed_changes") else "responder"


async def _apply_proposed_changes(
    proposed_changes: list[ProposedChange], *, execution_id: str | None, approved: bool | None
) -> tuple[list[str], list[str]]:
    """Actually write every proposed change to disk via the real
    create_file/write_file tools, persisting a code_changes row for each
    (diff, approved, and applied all recorded together — see
    apply_changes_node). Returns (applied file paths, error strings) — a
    per-file failure doesn't abort the rest of the batch.
    """
    applied: list[str] = []
    errors: list[str] = []
    for change in proposed_changes:
        tool_name = "create_file" if change["action"] == "create" else "write_file"
        result = await TOOLS_BY_NAME[tool_name].ainvoke(
            {"file_path": change["file_path"], "content": change["content"]}
        )
        succeeded = not str(result).startswith("Error")
        if succeeded:
            applied.append(change["file_path"])
        else:
            errors.append(str(result))

        if execution_id:
            change_type = "create" if change["action"] == "create" else "modify"
            await record_code_change(
                execution_id,
                change["file_path"],
                change_type,
                change["diff"],
                approved=approved,
                applied=succeeded,
            )

    return applied, errors


async def apply_changes_node(state: GraphState) -> dict:
    """Code modification stage — only reaches here after the human
    approval interrupt has been resumed. If the human rejected the
    changes, nothing is written; `route_after_apply` then skips testing
    and goes straight to the final response.
    """
    execution_id = state.get("execution_id")

    if not state.get("approved"):
        errors = list(state.get("errors", []))
        errors.append("Proposed changes were not approved; no files were modified.")
        if execution_id:
            for change in state.get("proposed_changes", []):
                change_type = "create" if change["action"] == "create" else "modify"
                await record_code_change(
                    execution_id, change["file_path"], change_type, change["diff"], approved=False, applied=False
                )
        return {"applied_changes": [], "errors": errors}

    applied, new_errors = await _apply_proposed_changes(
        state["proposed_changes"], execution_id=execution_id, approved=True
    )
    errors = list(state.get("errors", [])) + new_errors
    return {"applied_changes": applied, "errors": errors}


def route_after_apply(state: GraphState) -> Literal["run_tests", "responder"]:
    """Only run tests for changes that were actually approved and applied."""
    return "run_tests" if state.get("approved") else "responder"


def _split_test_output(raw: str) -> tuple[str, str | None]:
    """Split run_tests' combined "Exit code: N\\n--- stdout ---\\n...
    --- stderr ---\\n..." text (see app/core/command_safety.py) into
    separate output/error_output for the test_results table.
    """
    stdout_marker, stderr_marker = "--- stdout ---", "--- stderr ---"
    if stdout_marker in raw and stderr_marker in raw:
        stdout_part = raw.split(stdout_marker, 1)[1].split(stderr_marker, 1)[0].strip()
        stderr_part = raw.split(stderr_marker, 1)[1].strip()
        return stdout_part, stderr_part or None
    return raw, None


async def run_tests_node(state: GraphState) -> dict:
    """Run the test suite directly via the run_tests tool (not an LLM
    decision — verifying the change is always required after applying it).
    """
    output = await TOOLS_BY_NAME["run_tests"].ainvoke({})
    passed = output.startswith("Exit code: 0")

    execution_id = state.get("execution_id")
    if execution_id:
        await record_tool_call(execution_id, "run_tests", {}, output, success=passed)
        stdout_part, stderr_part = _split_test_output(output)
        await record_test_result(
            execution_id, get_settings().test_command, passed, stdout_part, stderr_part
        )

    return {"test_results": output, "test_passed": passed}


def route_after_tests(state: GraphState) -> Literal["error_analysis", "responder"]:
    """Tests passed -> done. Tests failed but retries remain -> attempt an
    automatic fix. Tests failed and retries are exhausted -> stop and
    report failure rather than looping forever.
    """
    if state.get("test_passed"):
        return "responder"
    if state.get("retry_count", 0) >= get_settings().max_retries:
        return "responder"
    return "error_analysis"


async def error_analysis_node(state: GraphState) -> dict:
    """Diagnose the test failure and propose a fix. This does not ask for
    fresh human approval before applying the fix (see code_fix_node) —
    only the initial change set is gated behind human approval; automatic
    retries stay within that same approved task and are capped by
    max_retries so the loop can't run away.
    """
    chain = ERROR_ANALYSIS_PROMPT | get_chat_model() | StrOutputParser()
    diagnosis = await chain.ainvoke(
        {"user_request": state["user_request"], "test_results": state["test_results"]}
    )

    instruction = (
        f"The previous change caused the test suite to fail.\n\n"
        f"Test output:\n{state['test_results']}\n\n"
        f"Diagnosis:\n{diagnosis}\n\n"
        "Propose the file changes needed to fix this."
    )

    return {
        "errors": list(state.get("errors", [])) + [diagnosis],
        "proposed_changes": await _propose_changes(instruction),
        "retry_count": state.get("retry_count", 0) + 1,
    }


async def code_fix_node(state: GraphState) -> dict:
    """Apply the fix proposed by error_analysis_node, then loop back to
    run_tests_node (see graph.py) to check whether it worked.
    """
    applied, new_errors = await _apply_proposed_changes(
        state.get("proposed_changes", []), execution_id=state.get("execution_id"), approved=state.get("approved")
    )
    return {
        "applied_changes": list(state.get("applied_changes", [])) + applied,
        "errors": list(state.get("errors", [])) + new_errors,
    }


def _render_outcome(state: GraphState) -> str:
    """Summarize what actually happened, for the responder to write up."""
    if not state.get("proposed_changes"):
        return "No code changes were needed for this request."

    lines = [f"Proposed changes: {[c['file_path'] for c in state['proposed_changes']]}"]
    lines.append(f"Approved by human reviewer: {state.get('approved')}")
    lines.append(f"Applied changes: {state.get('applied_changes', [])}")
    if state.get("test_results"):
        lines.append(f"Retry attempts used: {state.get('retry_count', 0)}")
        lines.append(f"Final test result: {'PASSED' if state.get('test_passed') else 'FAILED'}")
        lines.append(f"Test output:\n{state['test_results']}")
    if state.get("errors"):
        lines.append(f"Errors encountered:\n{state['errors']}")
    return "\n\n".join(lines)


async def responder_node(state: GraphState) -> dict:
    """Synthesize everything gathered and done so far into the final
    user-facing response. Execution status (completed/failed) is updated
    by AgentService, once the whole graph.ainvoke() call returns or
    raises — not here, since a raised exception means this node never
    runs at all.
    """
    chain = RESPONDER_PROMPT | get_chat_model() | StrOutputParser()
    final_response = await chain.ainvoke(
        {
            "user_request": state["user_request"],
            "plan": state["plan"],
            "analysis": state["analysis"],
            "outcome": _render_outcome(state),
        }
    )
    return {"final_response": final_response}
