from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.db.models.execution import Execution


class AgentPlan(Base):
    """`plan` stores planner_node's raw text output as-is (a short
    numbered list, per app/prompts/agent_prompts.py:PLANNER_PROMPT) —
    that's already what the spec calls "structured text"; wrapping it in
    JSON would just be re-encoding a string for no reader's benefit.
    """

    __tablename__ = "agent_plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), index=True
    )
    plan: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), default=utcnow)

    execution: Mapped["Execution"] = relationship(back_populates="agent_plans")
