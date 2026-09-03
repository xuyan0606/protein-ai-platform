"""add annotation and signal tables

Revision ID: c4d9e1b2f7aa
Revises: a3f7c9e2b1d4
Create Date: 2026-07-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4d9e1b2f7aa"
down_revision: Union[str, None] = "a3f7c9e2b1d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interpro_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("interpro_id", sa.String(length=32), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_db", sa.String(length=32), nullable=True),
        sa.Column("go_terms", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_interpro_entries_interpro_id", "interpro_entries", ["interpro_id"], unique=True)

    op.create_table(
        "enzyme_interpro_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("enzyme_id", sa.Integer(), sa.ForeignKey("enzyme_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interpro_entry_id", sa.Integer(), sa.ForeignKey("interpro_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_pos", sa.Integer(), nullable=True),
        sa.Column("end_pos", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("evidence", sa.String(length=32), nullable=True),
        sa.UniqueConstraint("enzyme_id", "interpro_entry_id", "start_pos", "end_pos", name="uq_enzyme_interpro_region"),
    )
    op.create_index("ix_enzyme_interpro_enzyme", "enzyme_interpro_links", ["enzyme_id"], unique=False)

    op.create_table(
        "catalytic_sites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("enzyme_id", sa.Integer(), sa.ForeignKey("enzyme_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("mechanism_name", sa.String(length=500), nullable=True),
        sa.Column("reaction_text", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_catalytic_site_enzyme", "catalytic_sites", ["enzyme_id"], unique=False)

    op.create_table(
        "catalytic_residues",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("catalytic_sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("residue_pos", sa.Integer(), nullable=False),
        sa.Column("residue_aa", sa.String(length=4), nullable=True),
        sa.Column("role", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("pdb_chain", sa.String(length=8), nullable=True),
        sa.Column("pdb_residue_no", sa.String(length=16), nullable=True),
    )
    op.create_index("ix_catalytic_residue_pos", "catalytic_residues", ["residue_pos"], unique=False)

    op.create_table(
        "signal_peptide_predictions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("enzyme_id", sa.Integer(), sa.ForeignKey("enzyme_records.id", ondelete="CASCADE"), nullable=True),
        sa.Column("sequence_hash", sa.String(length=64), nullable=False),
        sa.Column("has_signal", sa.Boolean(), nullable=True),
        sa.Column("cleavage_site", sa.String(length=32), nullable=True),
        sa.Column("model_name", sa.String(length=64), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_signal_peptide_predictions_sequence_hash", "signal_peptide_predictions", ["sequence_hash"], unique=False)
    op.create_index("ix_signal_peptide_enzyme", "signal_peptide_predictions", ["enzyme_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_signal_peptide_enzyme", table_name="signal_peptide_predictions")
    op.drop_index("ix_signal_peptide_predictions_sequence_hash", table_name="signal_peptide_predictions")
    op.drop_table("signal_peptide_predictions")

    op.drop_index("ix_catalytic_residue_pos", table_name="catalytic_residues")
    op.drop_table("catalytic_residues")

    op.drop_index("ix_catalytic_site_enzyme", table_name="catalytic_sites")
    op.drop_table("catalytic_sites")

    op.drop_index("ix_enzyme_interpro_enzyme", table_name="enzyme_interpro_links")
    op.drop_table("enzyme_interpro_links")

    op.drop_index("ix_interpro_entries_interpro_id", table_name="interpro_entries")
    op.drop_table("interpro_entries")
