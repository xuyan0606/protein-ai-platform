"""add user status controls

Revision ID: 7c2a1d4e9b66
Revises: 0d4a9f1c8b23
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c2a1d4e9b66"
down_revision: Union[str, None] = "0d4a9f1c8b23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("disabled_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "disabled_reason")
    op.drop_column("users", "locked_at")
    op.drop_column("users", "is_active")
