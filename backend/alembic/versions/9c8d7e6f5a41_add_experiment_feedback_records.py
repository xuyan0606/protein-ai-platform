"""add experiment feedback records

Revision ID: 9c8d7e6f5a41
Revises: 2f6c8d9e0a12
Create Date: 2026-07-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c8d7e6f5a41"
down_revision: Union[str, None] = "2f6c8d9e0a12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiment_feedback_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(length=16), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("linked_task_id", sa.String(length=128), nullable=True),
        sa.Column("enzyme_name", sa.String(length=255), nullable=True),
        sa.Column("variant_name", sa.String(length=128), nullable=False),
        sa.Column("parent_variant", sa.String(length=128), nullable=True),
        sa.Column("mutations", sa.JSON(), nullable=False),
        sa.Column("assay_payload", sa.JSON(), nullable=True),
        sa.Column("metrics_payload", sa.JSON(), nullable=True),
        sa.Column("quality_payload", sa.JSON(), nullable=True),
        sa.Column("interpretation_payload", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_experiment_feedback_records_created_by_user_id", "experiment_feedback_records", ["created_by_user_id"], unique=False)
    op.create_index("ix_experiment_feedback_records_project_id", "experiment_feedback_records", ["project_id"], unique=False)
    op.create_index("ix_experiment_feedback_records_linked_task_id", "experiment_feedback_records", ["linked_task_id"], unique=False)
    op.create_index("ix_experiment_feedback_records_enzyme_name", "experiment_feedback_records", ["enzyme_name"], unique=False)
    op.create_index("ix_experiment_feedback_records_variant_name", "experiment_feedback_records", ["variant_name"], unique=False)
    op.create_index("ix_experiment_feedback_records_parent_variant", "experiment_feedback_records", ["parent_variant"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_experiment_feedback_records_parent_variant", table_name="experiment_feedback_records")
    op.drop_index("ix_experiment_feedback_records_variant_name", table_name="experiment_feedback_records")
    op.drop_index("ix_experiment_feedback_records_enzyme_name", table_name="experiment_feedback_records")
    op.drop_index("ix_experiment_feedback_records_linked_task_id", table_name="experiment_feedback_records")
    op.drop_index("ix_experiment_feedback_records_project_id", table_name="experiment_feedback_records")
    op.drop_index("ix_experiment_feedback_records_created_by_user_id", table_name="experiment_feedback_records")
    op.drop_table("experiment_feedback_records")
