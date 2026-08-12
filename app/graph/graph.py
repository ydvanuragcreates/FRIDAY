from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import (
    agent_node,
    analyzer_node,
    planner_node,
    responder_node,
    route_after_agent,
    tool_node,
)
from app.graph.state import GraphState


def build_graph() -> CompiledStateGraph:
    """Wire up the coding-agent workflow:

        START -> planner -> agent -> [tools -> agent]* -> analyzer -> responder -> END

    `agent` and `tools` form a loop: after `agent` runs, `route_after_agent`
    checks whether it just requested tool calls. If so, execution goes to
    `tools`, which always routes straight back to `agent`. If not, `agent`
    is done gathering information and execution moves on to `analyzer`.
    LangGraph's default recursion limit caps how many times this loop can
    run, guarding against a runaway tool-calling loop.
    """
    graph_builder = StateGraph(GraphState)

    graph_builder.add_node("planner", planner_node)
    graph_builder.add_node("agent", agent_node)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("analyzer", analyzer_node)
    graph_builder.add_node("responder", responder_node)

    graph_builder.add_edge(START, "planner")
    graph_builder.add_edge("planner", "agent")
    graph_builder.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "analyzer": "analyzer"},
    )
    graph_builder.add_edge("tools", "agent")
    graph_builder.add_edge("analyzer", "responder")
    graph_builder.add_edge("responder", END)

    return graph_builder.compile()
