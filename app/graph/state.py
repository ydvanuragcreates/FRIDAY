from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GraphState(TypedDict):
    """Shared state that flows through the coding-agent graph.

    Every node reads whichever keys it needs and returns a dict containing
    only the keys it updates. For most fields, LangGraph's default merge
    behavior applies: a node's return value for that key REPLACES the old
    value.

    `messages` is the exception — it's annotated with the `add_messages`
    reducer, so a node returning `{"messages": [...]}` APPENDS those
    messages to the existing list instead of overwriting it. This is what
    lets the agent/tools loop accumulate a growing tool-calling
    conversation (AI tool requests + tool results) across multiple passes.
    """

    user_request: str
    plan: str
    messages: Annotated[list[BaseMessage], add_messages]
    analysis: str
    final_response: str
