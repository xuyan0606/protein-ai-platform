"""add workflow shadow audits

Revision ID: 1a2b3c4d5e6f
Revises: 0d4a9f1c8b23
Create Date: 2026-08-28
"""

from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "a7c4e2f9b601"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_shadow_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.String(length=16), nullable=True),
        sa.Column("governance_version", sa.String(length=32), nullable=False),
        sa.Column("message_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("intent", sa.String(length=32), nullable=True),
        sa.Column("workflow_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("route_payload", sa.JSON(), nullable=False),
        sa.Column("comparison_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_shadow_audits_user_id", "workflow_shadow_audits", ["user_id"])
    op.create_index("ix_workflow_shadow_audits_conversation_id", "workflow_shadow_audits", ["conversation_id"])
    op.create_index("ix_workflow_shadow_audits_project_id", "workflow_shadow_audits", ["project_id"])
    op.create_index("ix_workflow_shadow_audits_message_fingerprint", "workflow_shadow_audits", ["message_fingerprint"])
    op.create_index("ix_workflow_shadow_audits_workflow_id", "workflow_shadow_audits", ["workflow_id"])
    op.create_index("ix_workflow_shadow_audits_created_at", "workflow_shadow_audits", ["created_at"])


def downgrade() -> None:
    for name in ("ix_workflow_shadow_audits_created_at", "ix_workflow_shadow_audits_workflow_id", "ix_workflow_shadow_audits_message_fingerprint", "ix_workflow_shadow_audits_project_id", "ix_workflow_shadow_audits_conversation_id", "ix_workflow_shadow_audits_user_id"):
        op.drop_index(name, table_name="workflow_shadow_audits")
    op.drop_table("workflow_shadow_audits")
