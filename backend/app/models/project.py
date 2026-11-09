"""Project workspace models for multi-sequence management."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, Float, Boolean, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow_naive


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)

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
    members: Mapped[list["ProjectMember"]] = relationship(
        "ProjectMember", back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )
    organization_grants: Mapped[list["ProjectOrganizationGrant"]] = relationship(
        "ProjectOrganizationGrant", back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )


class ProjectMember(Base):
    """Project-level access control entry."""

    __tablename__ = "project_members"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(16), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")  # viewer, editor
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    project: Mapped[Project] = relationship("Project", back_populates="members")

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member_user"),
    )


class Organization(Base):
    """Organization/team container for inherited project access."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember", back_populates="organization", cascade="all, delete-orphan", lazy="selectin"
    )
    project_grants: Mapped[list["ProjectOrganizationGrant"]] = relationship(
        "ProjectOrganizationGrant", back_populates="organization", cascade="all, delete-orphan", lazy="selectin"
    )


class OrganizationMember(Base):
    """Organization membership. Org admins can later manage org-level grants."""

    __tablename__ = "organization_members"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(16), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")  # member, admin
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    organization: Mapped[Organization] = relationship("Organization", back_populates="members")

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_member_user"),
    )


class ProjectOrganizationGrant(Base):
    """Project access inherited by all members of an organization."""

    __tablename__ = "project_organization_grants"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(16), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(16), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")  # viewer, editor
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    project: Mapped[Project] = relationship("Project", back_populates="organization_grants")
    organization: Mapped[Organization] = relationship("Organization", back_populates="project_grants")

    __table_args__ = (
        UniqueConstraint("project_id", "organization_id", name="uq_project_organization_grant"),
    )


class PermissionAudit(Base):
    """Append-only permission change audit for project/org access operations."""

    __tablename__ = "permission_audits"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_uuid)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    target_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    organization_id: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    role_before: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role_after: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class ProjectSequence(Base):
    __tablename__ = "project_sequences"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(16), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sequence: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    project: Mapped[Project] = relationship("Project", back_populates="sequences")


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(16), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, completed, failed
    total: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    project: Mapped[Project] = relationship("Project", back_populates="files")
