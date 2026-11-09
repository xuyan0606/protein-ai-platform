"""add literature tables

Revision ID: 8eb683a67e73
Revises:
Create Date: 2026-06-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8eb683a67e73"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- papers ---
    op.create_table(
        "papers",
        sa.Column("pmid", sa.String(20), primary_key=True),
        sa.Column("doi", sa.String(200), nullable=True, unique=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("authors", sa.Text, nullable=True),
        sa.Column("journal", sa.String(500), nullable=True),
        sa.Column("year", sa.Integer, nullable=True),
        sa.Column("abstract", sa.Text, nullable=True),
        sa.Column("mesh_terms", sa.Text, nullable=True),
        sa.Column("citation_count", sa.Integer, nullable=True),
        sa.Column("source", sa.String(20), server_default="pubmed"),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_paper_doi", "papers", ["doi"])
    op.create_index("ix_paper_year", "papers", ["year"])
    op.create_index("ix_paper_journal", "papers", ["journal"])

    # --- enzyme_literature_links ---
    op.create_table(
        "enzyme_literature_links",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "enzyme_id",
            sa.Integer,
            sa.ForeignKey("enzyme_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "paper_pmid",
            sa.String(20),
            sa.ForeignKey("papers.pmid", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(30), nullable=False, server_default="general"),
        sa.Column("source", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("relevance_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )
    op.create_unique_constraint(
        "uq_enzyme_paper_relation",
        "enzyme_literature_links",
        ["enzyme_id", "paper_pmid", "relation_type"],
    )
    op.create_index("ix_litlink_enzyme", "enzyme_literature_links", ["enzyme_id"])
    op.create_index("ix_litlink_paper", "enzyme_literature_links", ["paper_pmid"])
    op.create_index("ix_litlink_type", "enzyme_literature_links", ["relation_type"])


def downgrade() -> None:
    op.drop_table("enzyme_literature_links")
    op.drop_table("papers")
