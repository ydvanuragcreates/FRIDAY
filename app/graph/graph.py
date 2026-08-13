from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import (
    agent_node,
    analyzer_node,
    apply_changes_node,
    code_fix_node,
    error_analysis_node,
    implementer_node,
    planner_node,
    responder_node,
    route_after_agent,
    route_after_apply,
    route_after_implementer,
    route_after_tests,
    run_tests_node,
    tool_node,
)
from app.graph.state import GraphState


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """Wire up the coding-agent workflow:

        START -> planner -> agent -> [tools -> agent]*      (repository analysis)
              -> analyzer -> implementer                     (implementation plan)
              -> apply_changes                                (human approval, then code modification)
              -> run_tests -> [error_analysis -> code_fix -> run_tests]*  (fix-and-retest loop)
              -> responder -> END

    `agent` and `tools` form a loop: after `agent` runs, `route_after_agent`
    checks whether it just requested tool calls. If so, execution goes to
    `tools`, which always routes straight back to `agent`. LangGraph's
    default recursion limit caps how many times this loop can run, guarding
    against a runaway tool-calling loop.

    `run_tests`, `error_analysis`, and `code_fix` form the second loop: a
    failing test triggers an automatic diagnose-and-fix attempt, capped by
    `GraphState.retry_count` vs. `Settings.max_retries` (see
    `route_after_tests`) so it can't run forever either.

    The graph is compiled with `interrupt_before=["apply_changes"]`: once
    `implementer` has proposed changes, execution pauses right before they
    would be written to disk, and `AgentService` surfaces the plan + diffs
    to a human. Resuming (after `approved` is written into state via
    `update_state`) requires a checkpointer, which is why one is always
    attached here even if the caller doesn't supply one.

    Every node function in app/graph/nodes.py is `async def` (Phase 7) —
    LangGraph runs sync and async node callables interchangeably, so
    nothing about this wiring changes; the graph must be driven with
    `.ainvoke()`/`.aget_state()`/`.aupdate_state()` (see AgentService)
    rather than their sync counterparts.
    """
    graph_builder = StateGraph(GraphState)

    graph_builder.add_node("planner", planner_node)
    graph_builder.add_node("agent", agent_node)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("analyzer", analyzer_node)
    graph_builder.add_node("implementer", implementer_node)
    graph_builder.add_node("apply_changes", apply_changes_node)
    graph_builder.add_node("run_tests", run_tests_node)
    graph_builder.add_node("error_analysis", error_analysis_node)
    graph_builder.add_node("code_fix", code_fix_node)
    graph_builder.add_node("responder", responder_node)

    graph_builder.add_edge(START, "planner")
    graph_builder.add_edge("planner", "agent")
    graph_builder.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "analyzer": "analyzer"},
    )
    graph_builder.add_edge("tools", "agent")
    graph_builder.add_edge("analyzer", "implementer")
    graph_builder.add_conditional_edges(
        "implementer",
        route_after_implementer,
        {"apply_changes": "apply_changes", "responder": "responder"},
    )
    graph_builder.add_conditional_edges(
        "apply_changes",
        route_after_apply,
        {"run_tests": "run_tests", "responder": "responder"},
    )
    graph_builder.add_conditional_edges(
        "run_tests",
        route_after_tests,
        {"error_analysis": "error_analysis", "responder": "responder"},
    )
    graph_builder.add_edge("error_analysis", "code_fix")
    graph_builder.add_edge("code_fix", "run_tests")
    graph_builder.add_edge("responder", END)

    return graph_builder.compile(
        checkpointer=checkpointer or MemorySaver(),
        interrupt_before=["apply_changes"],
    )
