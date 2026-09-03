"""add persistent versioned identity consistency records"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7e5a1b2d9f0"
down_revision: Union[str, None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "identity_consistency_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_hash", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("evidence_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("identity", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint(
            "user_id", "sequence_hash", "model_version", "evidence_version", "identity",
            name="uq_identity_consistency_versioned",
        ),
    )
    op.create_index("ix_identity_consistency_records_user_id", "identity_consistency_records", ["user_id"], unique=False)
    op.create_index("ix_identity_consistency_records_sequence_hash", "identity_consistency_records", ["sequence_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_identity_consistency_records_sequence_hash", table_name="identity_consistency_records")
    op.drop_index("ix_identity_consistency_records_user_id", table_name="identity_consistency_records")
    op.drop_table("identity_consistency_records")
