"""add immutable analysis evidence snapshots

Revision ID: a7c4e2f9b601
Revises: f8a1c2d3e4b5
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c4e2f9b601"
down_revision: Union[str, None] = "f8a1c2d3e4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_evidence_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("base_analysis_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("evidence_snapshot_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("task_ids", sa.JSON(), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint("snapshot_id", name="uq_analysis_evidence_snapshots_snapshot_id"),
    )
    op.create_index("ix_analysis_evidence_snapshots_snapshot_id", "analysis_evidence_snapshots", ["snapshot_id"], unique=False)
    op.create_index("ix_analysis_evidence_snapshots_user_id", "analysis_evidence_snapshots", ["user_id"], unique=False)
    op.create_index("ix_analysis_evidence_snapshots_conversation_id", "analysis_evidence_snapshots", ["conversation_id"], unique=False)
    op.create_index("ix_analysis_evidence_snapshots_base_analysis_fingerprint", "analysis_evidence_snapshots", ["base_analysis_fingerprint"], unique=False)
    op.create_index("ix_analysis_evidence_snapshots_evidence_snapshot_fingerprint", "analysis_evidence_snapshots", ["evidence_snapshot_fingerprint"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_analysis_evidence_snapshots_evidence_snapshot_fingerprint", table_name="analysis_evidence_snapshots")
    op.drop_index("ix_analysis_evidence_snapshots_base_analysis_fingerprint", table_name="analysis_evidence_snapshots")
    op.drop_index("ix_analysis_evidence_snapshots_conversation_id", table_name="analysis_evidence_snapshots")
    op.drop_index("ix_analysis_evidence_snapshots_user_id", table_name="analysis_evidence_snapshots")
    op.drop_index("ix_analysis_evidence_snapshots_snapshot_id", table_name="analysis_evidence_snapshots")
    op.drop_table("analysis_evidence_snapshots")
