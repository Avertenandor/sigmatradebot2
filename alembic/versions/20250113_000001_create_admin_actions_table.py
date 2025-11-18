"""create admin_actions table

Revision ID: 20250113_000001
Revises: 20251117_000001
Create Date: 2025-01-13 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250113_000001"
down_revision: Union[str, None] = "20251117_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create admin_actions table
    op.create_table(
        "admin_actions",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["target_user_id"], ["users.id"], ondelete="SET NULL"
        ),
    )

    # Create indexes
    op.create_index("ix_admin_actions_admin_id", "admin_actions", ["admin_id"])
    op.create_index(
        "ix_admin_actions_action_type", "admin_actions", ["action_type"]
    )
    op.create_index(
        "ix_admin_actions_target_user_id", "admin_actions", ["target_user_id"]
    )
    op.create_index(
        "ix_admin_actions_created_at", "admin_actions", ["created_at"]
    )
    op.create_index(
        "idx_admin_action_admin_created",
        "admin_actions",
        ["admin_id", "created_at"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_admin_action_admin_created", table_name="admin_actions")
    op.drop_index("ix_admin_actions_created_at", table_name="admin_actions")
    op.drop_index(
        "ix_admin_actions_target_user_id", table_name="admin_actions"
    )
    op.drop_index("ix_admin_actions_action_type", table_name="admin_actions")
    op.drop_index("ix_admin_actions_admin_id", table_name="admin_actions")

    # Drop table
    op.drop_table("admin_actions")

