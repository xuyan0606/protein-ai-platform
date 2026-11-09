"""Persistent identity classifications used by the enzyme consistency guard."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IdentityConsistencyRecord(Base):
    __tablename__ = "identity_consistency_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    evidence_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    identity: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "user_id", "sequence_hash", "model_version", "evidence_version", "identity",
            name="uq_identity_consistency_versioned",
        ),
    )
