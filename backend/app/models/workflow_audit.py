"""Persistent, redacted audit records for shadow workflow decisions."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WorkflowShadowAudit(Base):
    __tablename__ = "workflow_shadow_audits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    governance_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v2-shadow-1")
    message_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    intent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    route_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    comparison_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
