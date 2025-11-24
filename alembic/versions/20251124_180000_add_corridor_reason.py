"""
Add reason column to deposit_corridor_history.

Revision ID: 20251124_180000
Revises: 20251124_120000
Create Date: 2025-11-24 18:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251124_180000"
down_revision = "20251124_120000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema by adding reason column."""
    op.add_column(
        "deposit_corridor_history",
        sa.Column("reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade database schema by removing reason column."""
    op.drop_column("deposit_corridor_history", "reason")


