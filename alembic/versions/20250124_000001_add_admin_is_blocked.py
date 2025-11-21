"""add admin is_blocked field

Revision ID: 20250124_000001
Revises: 20250120_000001
Create Date: 2025-01-24 00:00:01.000000

R10-3: Add is_blocked field to Admin model for compromised admin protection.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20250124_000001"
down_revision: Union[str, None] = "20250120_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # R10-3: Add is_blocked field to admins table
    op.add_column(
        "admins",
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default="false"),
    )
    # Create index for fast lookup of blocked admins
    op.create_index(
        "ix_admins_is_blocked",
        "admins",
        ["is_blocked"],
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_admins_is_blocked", table_name="admins")
    # Drop column
    op.drop_column("admins", "is_blocked")

