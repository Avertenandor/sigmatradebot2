"""add_suspicious_column_to_users

Revision ID: 09a510e1cd9d
Revises: 20250124_000005
Create Date: 2025-11-22 07:02:26.330400

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09a510e1cd9d'
down_revision: Union[str, None] = '20250124_000005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add suspicious column to users table."""
    op.add_column(
        "users",
        sa.Column("suspicious", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_users_suspicious", "users", ["suspicious"])


def downgrade() -> None:
    """Remove suspicious column from users table."""
    op.drop_index("ix_users_suspicious", table_name="users")
    op.drop_column("users", "suspicious")

