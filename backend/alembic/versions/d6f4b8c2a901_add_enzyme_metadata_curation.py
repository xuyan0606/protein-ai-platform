"""add enzyme metadata curation queue

Revision ID: d6f4b8c2a901
Revises: 9c8d7e6f5a41
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d6f4b8c2a901"
down_revision: Union[str, None] = "9c8d7e6f5a41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enzyme_metadata_curation_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("paper_id", sa.String(length=128), nullable=False),
        sa.Column("record_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decision", sa.String(length=128), nullable=True),
        sa.Column("source_identifier", sa.String(length=255), nullable=True),
        sa.Column("source_manifest_path", sa.Text(), nullable=True),
        sa.Column("decision_payload", sa.JSON(), nullable=False),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("family", "paper_id", "record_type", name="uq_enzyme_metadata_curation_record_identity"),
    )
    op.create_index("ix_enzyme_metadata_curation_records_family", "enzyme_metadata_curation_records", ["family"], unique=False)
    op.create_index("ix_enzyme_metadata_curation_records_paper_id", "enzyme_metadata_curation_records", ["paper_id"], unique=False)
    op.create_index("ix_enzyme_metadata_curation_records_record_type", "enzyme_metadata_curation_records", ["record_type"], unique=False)
    op.create_index("ix_enzyme_metadata_curation_records_status", "enzyme_metadata_curation_records", ["status"], unique=False)
    op.create_index("ix_enzyme_metadata_curation_records_created_by_user_id", "enzyme_metadata_curation_records", ["created_by_user_id"], unique=False)
    op.create_index("ix_enzyme_metadata_curation_records_reviewed_by_user_id", "enzyme_metadata_curation_records", ["reviewed_by_user_id"], unique=False)
    op.create_index("ix_enzyme_metadata_curation_records_decision", "enzyme_metadata_curation_records", ["decision"], unique=False)

    op.create_table(
        "enzyme_metadata_curation_batches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_key", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("archived_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("family", sa.String(length=64), nullable=True),
        sa.Column("record_type", sa.String(length=64), nullable=True),
        sa.Column("record_ids", sa.JSON(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("export_payload", sa.JSON(), nullable=False),
        sa.Column("confirmation_token", sa.String(length=128), nullable=False),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("batch_key", name="uq_enzyme_metadata_curation_batch_key"),
    )
    op.create_index("ix_enzyme_metadata_curation_batches_batch_key", "enzyme_metadata_curation_batches", ["batch_key"], unique=False)
    op.create_index("ix_enzyme_metadata_curation_batches_status", "enzyme_metadata_curation_batches", ["status"], unique=False)
    op.create_index("ix_enzyme_metadata_curation_batches_created_by_user_id", "enzyme_metadata_curation_batches", ["created_by_user_id"], unique=False)
    op.create_index("ix_enzyme_metadata_curation_batches_archived_by_user_id", "enzyme_metadata_curation_batches", ["archived_by_user_id"], unique=False)
    op.create_index("ix_enzyme_metadata_curation_batches_family", "enzyme_metadata_curation_batches", ["family"], unique=False)
    op.create_index("ix_enzyme_metadata_curation_batches_record_type", "enzyme_metadata_curation_batches", ["record_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_enzyme_metadata_curation_batches_record_type", table_name="enzyme_metadata_curation_batches")
    op.drop_index("ix_enzyme_metadata_curation_batches_family", table_name="enzyme_metadata_curation_batches")
    op.drop_index("ix_enzyme_metadata_curation_batches_archived_by_user_id", table_name="enzyme_metadata_curation_batches")
    op.drop_index("ix_enzyme_metadata_curation_batches_created_by_user_id", table_name="enzyme_metadata_curation_batches")
    op.drop_index("ix_enzyme_metadata_curation_batches_status", table_name="enzyme_metadata_curation_batches")
    op.drop_index("ix_enzyme_metadata_curation_batches_batch_key", table_name="enzyme_metadata_curation_batches")
    op.drop_table("enzyme_metadata_curation_batches")

    op.drop_index("ix_enzyme_metadata_curation_records_decision", table_name="enzyme_metadata_curation_records")
    op.drop_index("ix_enzyme_metadata_curation_records_reviewed_by_user_id", table_name="enzyme_metadata_curation_records")
    op.drop_index("ix_enzyme_metadata_curation_records_created_by_user_id", table_name="enzyme_metadata_curation_records")
    op.drop_index("ix_enzyme_metadata_curation_records_status", table_name="enzyme_metadata_curation_records")
    op.drop_index("ix_enzyme_metadata_curation_records_record_type", table_name="enzyme_metadata_curation_records")
    op.drop_index("ix_enzyme_metadata_curation_records_paper_id", table_name="enzyme_metadata_curation_records")
    op.drop_index("ix_enzyme_metadata_curation_records_family", table_name="enzyme_metadata_curation_records")
    op.drop_table("enzyme_metadata_curation_records")
