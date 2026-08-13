from datetime import datetime, timezone

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """Python-side default/onupdate for timestamp columns — used
    alongside (not instead of) `server_default=func.now()` on every model.
    The session factory sets `expire_on_commit=False` (so ORM objects
    stay usable after a request's session closes, e.g. for building a
    Pydantic response), which means a server-computed default is never
    automatically re-fetched into the in-memory object — reading it would
    trigger a lazy load outside any async context and raise
    `MissingGreenlet`. A Python-side default sidesteps that entirely:
    SQLAlchemy computes it before sending the INSERT/UPDATE, so the
    in-memory object already has the real value with no extra round trip.
    The server_default stays too, as a fallback for writes that don't go
    through this ORM (raw SQL, manual backfills).
    """
    return datetime.now(timezone.utc)

# A fixed naming convention so Alembic autogenerate produces stable,
# predictable constraint/index names across migrations instead of
# dialect-assigned ones — matters most once a later migration needs to
# ALTER or DROP a constraint by name.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base for every ORM model in app/db/models/."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
