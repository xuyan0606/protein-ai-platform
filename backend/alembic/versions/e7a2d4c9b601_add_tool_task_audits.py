"""add tool task audits

Revision ID: e7a2d4c9b601
Revises: c4d9e1b2f7aa
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7a2d4c9b601"
down_revision: Union[str, None] = "c4d9e1b2f7aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_task_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("queue", sa.String(length=64), nullable=True),
        sa.Column("soft_time_limit", sa.Integer(), nullable=True),
        sa.Column("time_limit", sa.Integer(), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("stage", sa.String(length=128), nullable=True),
        sa.Column("input_summary", sa.JSON(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("artifact_manifest", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("terminal_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint("task_id", name="uq_tool_task_audit_task_id"),
    )
    op.create_index("ix_tool_task_audits_task_id", "tool_task_audits", ["task_id"], unique=False)
    op.create_index("ix_tool_task_audits_user_id", "tool_task_audits", ["user_id"], unique=False)
    op.create_index("ix_tool_task_audits_tool_name", "tool_task_audits", ["tool_name"], unique=False)
    op.create_index("ix_tool_task_audits_status", "tool_task_audits", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tool_task_audits_status", table_name="tool_task_audits")
    op.drop_index("ix_tool_task_audits_tool_name", table_name="tool_task_audits")
    op.drop_index("ix_tool_task_audits_user_id", table_name="tool_task_audits")
    op.drop_index("ix_tool_task_audits_task_id", table_name="tool_task_audits")
    op.drop_table("tool_task_audits")
