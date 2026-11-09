"""Strategy checkpoint and wet-lab calibration state models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StrategyCheckpoint(Base):
    """Persisted strategy shown to the user before confirmed execution."""

    __tablename__ = "strategy_checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(16), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    task_text: Mapped[str] = mapped_column(Text, nullable=False)
    task_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    strategy_signature: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="awaiting_confirmation", index=True)
    next_action: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    plan_payload: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    evidence_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    artifacts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    policy_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("conversation_id", "strategy_signature", "revision", name="uq_strategy_checkpoint_revision"),
    )


class AnalysisEvidenceSnapshot(Base):
    """Immutable, explicitly requested async-evidence snapshot.

    This is an input to a future analysis/report revision, never a mutable
    report itself.  Retaining it prevents a later renderer from silently
    consuming a changed task result.
    """

    __tablename__ = "analysis_evidence_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    base_analysis_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    evidence_snapshot_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence_payload: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WetLabCalibrationRun(Base):
    """Project-level calibration summary derived from wet-lab feedback records."""

    __tablename__ = "wet_lab_calibration_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(16), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    enzyme_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    objective: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    assay_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    dataset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    feedback_record_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    measured_variant_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    go_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    watch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    no_go_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hit_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_quality_grade: Mapped[str] = mapped_column(String(32), nullable=False, default="insufficient")
    evidence_level: Mapped[str] = mapped_column(String(32), nullable=False, default="computational_hypothesis")
    calibration_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "project_id", "objective", "dataset_fingerprint", name="uq_wet_lab_calibration_dataset"),
    )
