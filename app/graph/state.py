from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ProposedChange(TypedDict):
    """One file change proposed by the implementer/error-analysis nodes,
    shown to the human reviewer before apply_changes writes it to disk.
    """

    file_path: str
    action: Literal["create", "write"]
    content: str
    diff: str


class GraphState(TypedDict):
    """Shared state that flows through the coding-agent graph.

    Every node reads whichever keys it needs and returns a dict containing
    only the keys it updates. For most fields, LangGraph's default merge
    behavior applies: a node's return value for that key REPLACES the old
    value. Fields that need to accumulate across multiple passes through a
    loop (`files_inspected`, `applied_changes`, `errors`) are grown
    manually inside the node — the node reads the current list out of
    `state`, appends to it, and returns the whole new list.

    `messages` is the exception with automatic accumulation — it's
    annotated with the `add_messages` reducer, so a node returning
    `{"messages": [...]}` APPENDS those messages to the existing list
    instead of overwriting it. This is what lets the agent/tools loop
    accumulate a growing tool-calling conversation (AI tool requests + tool
    results) across multiple passes.
    """

    # Set once, at the start of the run. All three are `None` for the
    # plain /api/chat and /api/tasks entry points (Phases 4/5) — every
    # persist_* call in app/graph/nodes.py checks execution_id and is a
    # no-op when it's None, so those paths are completely unaffected by
    # Phase 7's persistence layer. Populated together, or not at all: a
    # conversation-message run (app/services/conversation_service.py)
    # sets all three, with execution_id doubling as the LangGraph
    # checkpointer thread_id (see app/services/agent_service.py).
    project_id: str | None
    conversation_id: str | None
    execution_id: str | None

    user_request: str

    # Repository-analysis phase (planner -> agent <-> tools -> analyzer).
    plan: str
    messages: Annotated[list[BaseMessage], add_messages]
    analysis: str
    files_inspected: list[str]

    # Implementation-plan / human-approval / code-modification phase.
    proposed_changes: list[ProposedChange]
    approved: bool | None
    applied_changes: list[str]

    # Test / fix-and-retry phase.
    test_results: str
    test_passed: bool
    errors: list[str]
    retry_count: int

    # Set once, at the end of the run.
    final_response: str
