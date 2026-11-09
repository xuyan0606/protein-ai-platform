"""add strategy checkpoints and wet lab calibration

Revision ID: f8a1c2d3e4b5
Revises: d6f4b8c2a901
Create Date: 2026-08-11
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8a1c2d3e4b5"
down_revision: Union[str, None] = "d6f4b8c2a901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(length=16), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_text", sa.Text(), nullable=False),
        sa.Column("task_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("strategy_signature", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="awaiting_confirmation"),
        sa.Column("next_action", sa.String(length=64), nullable=True),
        sa.Column("plan_payload", sa.JSON(), nullable=False),
        sa.Column("evidence_state", sa.JSON(), nullable=True),
        sa.Column("artifacts", sa.JSON(), nullable=True),
        sa.Column("policy_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("conversation_id", "strategy_signature", "revision", name="uq_strategy_checkpoint_revision"),
    )
    op.create_index("ix_strategy_checkpoints_user_id", "strategy_checkpoints", ["user_id"], unique=False)
    op.create_index("ix_strategy_checkpoints_conversation_id", "strategy_checkpoints", ["conversation_id"], unique=False)
    op.create_index("ix_strategy_checkpoints_project_id", "strategy_checkpoints", ["project_id"], unique=False)
    op.create_index("ix_strategy_checkpoints_task_fingerprint", "strategy_checkpoints", ["task_fingerprint"], unique=False)
    op.create_index("ix_strategy_checkpoints_strategy_signature", "strategy_checkpoints", ["strategy_signature"], unique=False)
    op.create_index("ix_strategy_checkpoints_status", "strategy_checkpoints", ["status"], unique=False)
    op.create_index("ix_strategy_checkpoints_next_action", "strategy_checkpoints", ["next_action"], unique=False)

    op.create_table(
        "wet_lab_calibration_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(length=16), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("enzyme_name", sa.String(length=255), nullable=True),
        sa.Column("objective", sa.String(length=64), nullable=False),
        sa.Column("assay_key", sa.String(length=128), nullable=True),
        sa.Column("dataset_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("feedback_record_ids", sa.JSON(), nullable=False),
        sa.Column("measured_variant_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("go_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("watch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("no_go_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hit_rate", sa.Float(), nullable=True),
        sa.Column("data_quality_grade", sa.String(length=32), nullable=False, server_default="insufficient"),
        sa.Column("evidence_level", sa.String(length=32), nullable=False, server_default="computational_hypothesis"),
        sa.Column("calibration_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint("user_id", "project_id", "objective", "dataset_fingerprint", name="uq_wet_lab_calibration_dataset"),
    )
    op.create_index("ix_wet_lab_calibration_runs_user_id", "wet_lab_calibration_runs", ["user_id"], unique=False)
    op.create_index("ix_wet_lab_calibration_runs_project_id", "wet_lab_calibration_runs", ["project_id"], unique=False)
    op.create_index("ix_wet_lab_calibration_runs_enzyme_name", "wet_lab_calibration_runs", ["enzyme_name"], unique=False)
    op.create_index("ix_wet_lab_calibration_runs_objective", "wet_lab_calibration_runs", ["objective"], unique=False)
    op.create_index("ix_wet_lab_calibration_runs_assay_key", "wet_lab_calibration_runs", ["assay_key"], unique=False)
    op.create_index("ix_wet_lab_calibration_runs_dataset_fingerprint", "wet_lab_calibration_runs", ["dataset_fingerprint"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_wet_lab_calibration_runs_dataset_fingerprint", table_name="wet_lab_calibration_runs")
    op.drop_index("ix_wet_lab_calibration_runs_assay_key", table_name="wet_lab_calibration_runs")
    op.drop_index("ix_wet_lab_calibration_runs_objective", table_name="wet_lab_calibration_runs")
    op.drop_index("ix_wet_lab_calibration_runs_enzyme_name", table_name="wet_lab_calibration_runs")
    op.drop_index("ix_wet_lab_calibration_runs_project_id", table_name="wet_lab_calibration_runs")
    op.drop_index("ix_wet_lab_calibration_runs_user_id", table_name="wet_lab_calibration_runs")
    op.drop_table("wet_lab_calibration_runs")

    op.drop_index("ix_strategy_checkpoints_next_action", table_name="strategy_checkpoints")
    op.drop_index("ix_strategy_checkpoints_status", table_name="strategy_checkpoints")
    op.drop_index("ix_strategy_checkpoints_strategy_signature", table_name="strategy_checkpoints")
    op.drop_index("ix_strategy_checkpoints_task_fingerprint", table_name="strategy_checkpoints")
    op.drop_index("ix_strategy_checkpoints_project_id", table_name="strategy_checkpoints")
    op.drop_index("ix_strategy_checkpoints_conversation_id", table_name="strategy_checkpoints")
    op.drop_index("ix_strategy_checkpoints_user_id", table_name="strategy_checkpoints")
    op.drop_table("strategy_checkpoints")
