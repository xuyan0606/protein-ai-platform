"""add user roles

Revision ID: f1b9c8d2a704
Revises: e7a2d4c9b601
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1b9c8d2a704"
down_revision: Union[str, None] = "e7a2d4c9b601"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(length=32), nullable=False, server_default="researcher"))


def downgrade() -> None:
    op.drop_column("users", "role")
