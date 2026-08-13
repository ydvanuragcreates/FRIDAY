from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.db.models.execution import Execution


class ChangeType(str, enum.Enum):
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


class CodeChange(Base):
    """Written once, in apply_changes_node/code_fix_node, at the point
    `diff`, `approved`, and `applied` are all simultaneously known — see
    README > "How LangGraph talks to the database" for why this isn't a
    separate propose-then-update pair of writes.
    """

    __tablename__ = "code_changes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), index=True
    )
    file_path: Mapped[str] = mapped_column(String(1024))
    change_type: Mapped[ChangeType] = mapped_column(Enum(ChangeType, native_enum=False, length=20))
    diff: Mapped[str] = mapped_column(Text)
    approved: Mapped[bool | None] = mapped_column(Boolean, default=None)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), default=utcnow)

    execution: Mapped["Execution"] = relationship(back_populates="code_changes")
