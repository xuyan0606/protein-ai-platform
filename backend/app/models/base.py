"""Declarative base with SQLAlchemy 2.0 Mapped[] style annotations."""

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


def utcnow_naive() -> datetime:
    """Return the current UTC time without tzinfo for existing DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass
