from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.db.models.execution import Execution


class ToolCallStatus(str, enum.Enum):
    SUCCESS = "success"
    ERROR = "error"


class ToolCall(Base):
    """`input`/`output` are redacted (see app/services/redaction.py)
    before they ever reach this table — a tool_call is exactly where a
    read_file call on a .env file would otherwise leak a real secret into
    the database.
    """

    __tablename__ = "tool_calls"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(255))
    input: Mapped[dict[str, Any]] = mapped_column(JSON)
    output: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[ToolCallStatus] = mapped_column(Enum(ToolCallStatus, native_enum=False, length=20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), default=utcnow)

    execution: Mapped["Execution"] = relationship(back_populates="tool_calls")
