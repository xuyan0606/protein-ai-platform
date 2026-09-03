"""Platform-side curation queue for simple enzyme metadata policy decisions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EnzymeMetadataCurationRecord(Base):
    """Materialized review record from acid/xylanase policy sidecars."""

    __tablename__ = "enzyme_metadata_curation_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    paper_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    record_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    decision: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_manifest_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("family", "paper_id", "record_type", name="uq_enzyme_metadata_curation_record_identity"),
    )


class EnzymeMetadataCurationBatch(Base):
    """Internal archive batch for reviewed simple-enzyme metadata decisions."""

    __tablename__ = "enzyme_metadata_curation_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="prepared", index=True)
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    archived_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    family: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    record_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    record_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    export_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    confirmation_token: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("batch_key", name="uq_enzyme_metadata_curation_batch_key"),
    )
