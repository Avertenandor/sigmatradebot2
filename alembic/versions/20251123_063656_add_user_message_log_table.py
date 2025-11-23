"""Add user_message_logs table.

Revision ID: 20251123_063656
Revises: 
Create Date: 2025-11-23 06:36:56

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251123_063656"
down_revision: str | None = "09a510e1cd9d"  # add_suspicious_column_to_users
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create user_message_logs table
    op.create_table(
        "user_message_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(
        "ix_user_message_logs_user_id",
        "user_message_logs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_message_logs_telegram_id",
        "user_message_logs",
        ["telegram_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_message_logs_created_at",
        "user_message_logs",
        ["created_at"],
        unique=False,
    )
    # Composite index for efficient queries
    op.create_index(
        "ix_user_message_logs_telegram_id_created_at",
        "user_message_logs",
        ["telegram_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade database schema."""
    # Drop indexes
    op.drop_index(
        "ix_user_message_logs_telegram_id_created_at",
        table_name="user_message_logs",
    )
    op.drop_index(
        "ix_user_message_logs_created_at",
        table_name="user_message_logs",
    )
    op.drop_index(
        "ix_user_message_logs_telegram_id",
        table_name="user_message_logs",
    )
    op.drop_index(
        "ix_user_message_logs_user_id",
        table_name="user_message_logs",
    )

    # Drop table
    op.drop_table("user_message_logs")

