"""add deposit versioning and user fields

Revision ID: 20250120_000001
Revises: 20251120_072315
Create Date: 2025-01-20 00:00:01.000000

R17-1, R17-2: Deposit level versioning
R8-2: User bot_blocked tracking
R12-1: Deposit completed_at timestamp
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250120_000001"
down_revision: Union[str, None] = "20251120_072315"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # R17-1, R17-2: Create deposit_level_versions table
    op.create_table(
        "deposit_level_versions",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("level_number", sa.Integer(), nullable=False),
        sa.Column("amount", sa.DECIMAL(10, 2), nullable=False),
        sa.Column("roi_percent", sa.DECIMAL(5, 2), nullable=False),
        sa.Column("roi_cap_percent", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["created_by_admin_id"], ["admins.id"], ondelete="SET NULL"
        ),
    )

    # Create indexes for deposit_level_versions
    op.create_index(
        "ix_deposit_level_versions_level_number",
        "deposit_level_versions",
        ["level_number"],
    )
    op.create_index(
        "ix_deposit_level_versions_version",
        "deposit_level_versions",
        ["version"],
    )
    op.create_index(
        "ix_deposit_level_versions_effective_from",
        "deposit_level_versions",
        ["effective_from"],
    )
    op.create_index(
        "ix_deposit_level_versions_is_active",
        "deposit_level_versions",
        ["is_active"],
    )

    # R17-1: Add deposit_version_id to deposits table
    op.add_column(
        "deposits",
        sa.Column("deposit_version_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_deposits_deposit_version_id",
        "deposits",
        "deposit_level_versions",
        ["deposit_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_deposits_deposit_version_id",
        "deposits",
        ["deposit_version_id"],
    )

    # R12-1: Add completed_at to deposits table
    op.add_column(
        "deposits",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # R8-2: Add bot_blocked and bot_blocked_at to users table
    op.add_column(
        "users",
        sa.Column("bot_blocked", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("bot_blocked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_bot_blocked", "users", ["bot_blocked"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_users_bot_blocked", table_name="users")
    op.drop_index("ix_deposits_deposit_version_id", table_name="deposits")
    op.drop_index(
        "ix_deposit_level_versions_is_active", table_name="deposit_level_versions"
    )
    op.drop_index(
        "ix_deposit_level_versions_effective_from",
        table_name="deposit_level_versions",
    )
    op.drop_index(
        "ix_deposit_level_versions_version", table_name="deposit_level_versions"
    )
    op.drop_index(
        "ix_deposit_level_versions_level_number",
        table_name="deposit_level_versions",
    )

    # Drop columns
    op.drop_column("users", "bot_blocked_at")
    op.drop_column("users", "bot_blocked")
    op.drop_column("deposits", "completed_at")
    op.drop_constraint(
        "fk_deposits_deposit_version_id", "deposits", type_="foreignkey"
    )
    op.drop_column("deposits", "deposit_version_id")

    # Drop table
    op.drop_table("deposit_level_versions")

