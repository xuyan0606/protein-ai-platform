"""Platform-side lipase curation queue records."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LipaseCurationRecord(Base):
    """User-submitted enrichment candidate for the read-only KWB lipase DB."""

    __tablename__ = "lipase_curation_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted", index=True)
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    paper_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pmid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enzyme_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mutation_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    linked_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    evidence_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    feedback_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LipaseCurationBatch(Base):
    """Controlled review batch for accepted lipase curation records."""

    __tablename__ = "lipase_curation_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="prepared", index=True)
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    published_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    record_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    export_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    confirmation_token: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("batch_key", name="uq_lipase_curation_batch_key"),
    )
