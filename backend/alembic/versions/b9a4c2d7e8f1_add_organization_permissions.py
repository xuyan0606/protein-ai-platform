"""add organization permissions

Revision ID: b9a4c2d7e8f1
Revises: 7c2a1d4e9b66
Create Date: 2026-07-08
"""

from __future__ import annotations

from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9a4c2d7e8f1"
down_revision: Union[str, None] = "7c2a1d4e9b66"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_owner_user_id"), "organizations", ["owner_user_id"], unique=False)

    op.create_table(
        "organization_members",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("organization_id", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_organization_member_user"),
    )
    op.create_index(op.f("ix_organization_members_organization_id"), "organization_members", ["organization_id"], unique=False)
    op.create_index(op.f("ix_organization_members_user_id"), "organization_members", ["user_id"], unique=False)

    op.create_table(
        "project_organization_grants",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("project_id", sa.String(length=16), nullable=False),
        sa.Column("organization_id", sa.String(length=16), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "organization_id", name="uq_project_organization_grant"),
    )
    op.create_index(op.f("ix_project_organization_grants_project_id"), "project_organization_grants", ["project_id"], unique=False)
    op.create_index(op.f("ix_project_organization_grants_organization_id"), "project_organization_grants", ["organization_id"], unique=False)

    op.create_table(
        "permission_audits",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.String(length=16), nullable=True),
        sa.Column("organization_id", sa.String(length=16), nullable=True),
        sa.Column("role_before", sa.String(length=32), nullable=True),
        sa.Column("role_after", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_permission_audits_actor_user_id"), "permission_audits", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_permission_audits_target_user_id"), "permission_audits", ["target_user_id"], unique=False)
    op.create_index(op.f("ix_permission_audits_project_id"), "permission_audits", ["project_id"], unique=False)
    op.create_index(op.f("ix_permission_audits_organization_id"), "permission_audits", ["organization_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_permission_audits_organization_id"), table_name="permission_audits")
    op.drop_index(op.f("ix_permission_audits_project_id"), table_name="permission_audits")
    op.drop_index(op.f("ix_permission_audits_target_user_id"), table_name="permission_audits")
    op.drop_index(op.f("ix_permission_audits_actor_user_id"), table_name="permission_audits")
    op.drop_table("permission_audits")
    op.drop_index(op.f("ix_project_organization_grants_organization_id"), table_name="project_organization_grants")
    op.drop_index(op.f("ix_project_organization_grants_project_id"), table_name="project_organization_grants")
    op.drop_table("project_organization_grants")
    op.drop_index(op.f("ix_organization_members_user_id"), table_name="organization_members")
    op.drop_index(op.f("ix_organization_members_organization_id"), table_name="organization_members")
    op.drop_table("organization_members")
    op.drop_index(op.f("ix_organizations_owner_user_id"), table_name="organizations")
    op.drop_table("organizations")
