"""add lipase curation records

Revision ID: 2f6c8d9e0a12
Revises: b9a4c2d7e8f1
Create Date: 2026-07-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2f6c8d9e0a12"
down_revision: Union[str, None] = "b9a4c2d7e8f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lipase_curation_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("paper_key", sa.String(length=128), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("pmid", sa.String(length=64), nullable=True),
        sa.Column("enzyme_name", sa.String(length=255), nullable=True),
        sa.Column("mutation_code", sa.String(length=64), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("linked_task_id", sa.String(length=128), nullable=True),
        sa.Column("evidence_payload", sa.JSON(), nullable=True),
        sa.Column("feedback_payload", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_lipase_curation_records_source_type", "lipase_curation_records", ["source_type"], unique=False)
    op.create_index("ix_lipase_curation_records_status", "lipase_curation_records", ["status"], unique=False)
    op.create_index("ix_lipase_curation_records_created_by_user_id", "lipase_curation_records", ["created_by_user_id"], unique=False)
    op.create_index("ix_lipase_curation_records_reviewed_by_user_id", "lipase_curation_records", ["reviewed_by_user_id"], unique=False)
    op.create_index("ix_lipase_curation_records_paper_key", "lipase_curation_records", ["paper_key"], unique=False)
    op.create_index("ix_lipase_curation_records_mutation_code", "lipase_curation_records", ["mutation_code"], unique=False)
    op.create_index("ix_lipase_curation_records_position", "lipase_curation_records", ["position"], unique=False)
    op.create_index("ix_lipase_curation_records_linked_task_id", "lipase_curation_records", ["linked_task_id"], unique=False)

    op.create_table(
        "lipase_curation_batches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("published_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=True),
        sa.Column("record_ids", sa.JSON(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("export_payload", sa.JSON(), nullable=False),
        sa.Column("confirmation_token", sa.String(length=128), nullable=False),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("batch_key", name="uq_lipase_curation_batch_key"),
    )
    op.create_index("ix_lipase_curation_batches_batch_key", "lipase_curation_batches", ["batch_key"], unique=False)
    op.create_index("ix_lipase_curation_batches_status", "lipase_curation_batches", ["status"], unique=False)
    op.create_index("ix_lipase_curation_batches_created_by_user_id", "lipase_curation_batches", ["created_by_user_id"], unique=False)
    op.create_index("ix_lipase_curation_batches_published_by_user_id", "lipase_curation_batches", ["published_by_user_id"], unique=False)
    op.create_index("ix_lipase_curation_batches_source_type", "lipase_curation_batches", ["source_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_lipase_curation_batches_source_type", table_name="lipase_curation_batches")
    op.drop_index("ix_lipase_curation_batches_published_by_user_id", table_name="lipase_curation_batches")
    op.drop_index("ix_lipase_curation_batches_created_by_user_id", table_name="lipase_curation_batches")
    op.drop_index("ix_lipase_curation_batches_status", table_name="lipase_curation_batches")
    op.drop_index("ix_lipase_curation_batches_batch_key", table_name="lipase_curation_batches")
    op.drop_table("lipase_curation_batches")

    op.drop_index("ix_lipase_curation_records_linked_task_id", table_name="lipase_curation_records")
    op.drop_index("ix_lipase_curation_records_position", table_name="lipase_curation_records")
    op.drop_index("ix_lipase_curation_records_mutation_code", table_name="lipase_curation_records")
    op.drop_index("ix_lipase_curation_records_paper_key", table_name="lipase_curation_records")
    op.drop_index("ix_lipase_curation_records_reviewed_by_user_id", table_name="lipase_curation_records")
    op.drop_index("ix_lipase_curation_records_created_by_user_id", table_name="lipase_curation_records")
    op.drop_index("ix_lipase_curation_records_status", table_name="lipase_curation_records")
    op.drop_index("ix_lipase_curation_records_source_type", table_name="lipase_curation_records")
    op.drop_table("lipase_curation_records")
