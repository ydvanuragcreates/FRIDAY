"""Importing this package registers every model on `Base`'s mapper
registry — required before `Base.metadata.create_all(...)` (tests) or
Alembic autogenerate can see the full schema, and before any
`Mapped[list["Other"]]` cross-model forward reference can be resolved.
"""

from app.db.models.agent_plan import AgentPlan
from app.db.models.code_change import ChangeType, CodeChange
from app.db.models.conversation import Conversation
from app.db.models.execution import Execution, ExecutionStatus
from app.db.models.message import Message, MessageRole
from app.db.models.project import Project
from app.db.models.test_result import TestResult
from app.db.models.tool_call import ToolCall, ToolCallStatus
from app.db.models.user import User

__all__ = [
    "AgentPlan",
    "ChangeType",
    "CodeChange",
    "Conversation",
    "Execution",
    "ExecutionStatus",
    "Message",
    "MessageRole",
    "Project",
    "TestResult",
    "ToolCall",
    "ToolCallStatus",
    "User",
]
