from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.db.models.agent_plan import AgentPlan
    from app.db.models.code_change import CodeChange
    from app.db.models.conversation import Conversation
    from app.db.models.project import Project
    from app.db.models.test_result import TestResult
    from app.db.models.tool_call import ToolCall


class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Execution(Base):
    """One complete LangGraph agent run. `id` doubles as the LangGraph
    checkpointer's `thread_id` — see app/services/agent_service.py — so
    the human-approval pause/resume from Phase 5 and this execution
    record are always the same run, never two things to keep in sync.
    """

    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), index=True, default=None
    )
    user_request: Mapped[str] = mapped_column(Text)
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, native_enum=False, length=30), default=ExecutionStatus.PENDING
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped["Project"] = relationship(back_populates="executions")
    conversation: Mapped["Conversation | None"] = relationship(back_populates="executions")
    agent_plans: Mapped[list["AgentPlan"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan", order_by="AgentPlan.created_at"
    )
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan", order_by="ToolCall.created_at"
    )
    code_changes: Mapped[list["CodeChange"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan", order_by="CodeChange.created_at"
    )
    test_results: Mapped[list["TestResult"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan", order_by="TestResult.created_at"
    )
