"""Wet-lab experiment feedback records for enzyme engineering loops."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExperimentFeedbackRecord(Base):
    """User-submitted wet-lab phenotype data for a variant or mutation set."""

    __tablename__ = "experiment_feedback_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(16), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    enzyme_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    variant_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    parent_variant: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    mutations: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    assay_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metrics_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    quality_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    interpretation_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
