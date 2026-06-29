"""add wiki knowledgebase schema

Adds project-files table, conversation→project FK, and Outline wiki fields
on the projects table for the Project Wiki Knowledgebase feature.

Revision ID: a3f7c9e2b1d4
Revises: 8eb683a67e73
Create Date: 2026-06-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a3f7c9e2b1d4"
down_revision: Union[str, None] = "8eb683a67e73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- conversations.project_id FK ---
    # Use batch_alter for SQLite compatibility
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.add_column(
            sa.Column("project_id", sa.String(16), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_conversations_project_id",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_conversations_project_id", ["project_id"])

    # --- projects wiki fields ---
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(
            sa.Column("outline_collection_id", sa.String(100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("outline_root_doc_id", sa.String(100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("wiki_auto_publish", sa.Boolean(), server_default="0", nullable=False)
        )

    # --- project_files table ---
    op.create_table(
        "project_files",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(16),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("object_name", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_size", sa.Integer(), server_default="0"),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("source", sa.String(30), server_default="agent"),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("outline_doc_id", sa.String(100), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_project_files_project_id", "project_files", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_files_project_id", table_name="project_files")
    op.drop_table("project_files")

    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("wiki_auto_publish")
        batch_op.drop_column("outline_root_doc_id")
        batch_op.drop_column("outline_collection_id")

    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_index("ix_conversations_project_id")
        batch_op.drop_constraint("fk_conversations_project_id", type_="foreignkey")
        batch_op.drop_column("project_id")
