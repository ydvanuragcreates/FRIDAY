from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser

from app.core.llm import get_chat_model
from app.graph.state import GraphState
from app.prompts.agent_prompts import (
    AGENT_SYSTEM_PROMPT,
    ANALYZER_PROMPT,
    PLANNER_PROMPT,
    RESPONDER_PROMPT,
)
from app.tools import ALL_TOOLS

TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}


def planner_node(state: GraphState) -> dict:
    """Turn the raw user request into a short, concrete plan."""
    chain = PLANNER_PROMPT | get_chat_model() | StrOutputParser()
    plan = chain.invoke({"user_request": state["user_request"]})
    return {"plan": plan}


def agent_node(state: GraphState) -> dict:
    """Decide whether another tool call is needed to gather information, or
    whether enough has been gathered already.

    Runs in a loop with `tool_node` (see graph.py's conditional edge): each
    pass either ends in another round of tool requests or in a plain-text
    summary of findings with no tool calls, which ends the loop.
    """
    llm_with_tools = get_chat_model().bind_tools(ALL_TOOLS)

    if not state["messages"]:
        # First pass through the loop — seed the tool-calling conversation
        # from the user's request and the plan produced upstream.
        seed: list[BaseMessage] = [
            SystemMessage(content=AGENT_SYSTEM_PROMPT),
            HumanMessage(
                content=f"User request: {state['user_request']}\n\nPlan:\n{state['plan']}"
            ),
        ]
        response = llm_with_tools.invoke(seed)
        return {"messages": [*seed, response]}

    # Later passes — the message history already holds the seed plus any
    # prior tool calls/results; just continue the conversation.
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


def tool_node(state: GraphState) -> dict:
    """Execute every tool call requested in the agent's last message and
    return the results as ToolMessages, each tagged with the matching
    tool_call_id so the model can correlate a result back to its request.
    """
    last_message = state["messages"][-1]
    results: list[ToolMessage] = []

    for tool_call in last_message.tool_calls:
        tool_fn = TOOLS_BY_NAME.get(tool_call["name"])
        if tool_fn is None:
            content = f"Error: unknown tool '{tool_call['name']}'"
        else:
            try:
                content = tool_fn.invoke(tool_call["args"])
            except Exception as exc:  # surface any tool failure to the model, don't crash the graph
                content = f"Error: tool '{tool_call['name']}' failed: {exc}"

        results.append(ToolMessage(content=str(content), tool_call_id=tool_call["id"]))

    return {"messages": results}


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


def analyzer_node(state: GraphState) -> dict:
    """Analyze the request, plan, and everything gathered via tool calls."""
    findings = _render_agent_transcript(state["messages"])
    chain = ANALYZER_PROMPT | get_chat_model() | StrOutputParser()
    analysis = chain.invoke(
        {
            "user_request": state["user_request"],
            "plan": state["plan"],
            "findings": findings,
        }
    )
    return {"analysis": analysis}


def responder_node(state: GraphState) -> dict:
    """Synthesize the plan and analysis into the final user-facing response."""
    chain = RESPONDER_PROMPT | get_chat_model() | StrOutputParser()
    final_response = chain.invoke(
        {
            "user_request": state["user_request"],
            "plan": state["plan"],
            "analysis": state["analysis"],
        }
    )
    return {"final_response": final_response}
