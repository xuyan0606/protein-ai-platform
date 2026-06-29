"""Project workspace models for multi-sequence management."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, Float, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _uuid() -> str:
    return uuid.uuid4().hex[:16]


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    outline_collection_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    outline_root_doc_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    wiki_auto_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sequences: Mapped[list[ProjectSequence]] = relationship(
        "ProjectSequence", back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )
    batch_jobs: Mapped[list[BatchJob]] = relationship(
        "BatchJob", back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )
    files: Mapped[list["ProjectFile"]] = relationship(
        "ProjectFile", back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="project", lazy="selectin"
    )


class ProjectSequence(Base):
    __tablename__ = "project_sequences"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(16), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sequence: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped[Project] = relationship("Project", back_populates="sequences")


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(16), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, completed, failed
    total: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped[Project] = relationship("Project", back_populates="batch_jobs")


class ProjectFile(Base):
    """File metadata for project knowledge base (MinIO-backed, .md reports + attachments)."""
    __tablename__ = "project_files"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)  # display name
    object_name: Mapped[str] = mapped_column(String(500), nullable=False)  # MinIO path
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)  # md, pdb, csv, fasta, json
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256
    source: Mapped[str] = mapped_column(String(30), default="agent")  # agent, upload, batch, manual
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outline_doc_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped[Project] = relationship("Project", back_populates="files")
