"""add emergency stop flags to global_settings

Revision ID: 20251129_add_emergency_stops_to_global_settings
Revises: 20251128_null_sess
Create Date: 2025-11-29

R17-3: Add emergency stop flags for deposits, withdrawals and ROI accruals.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251129_add_emergency_stops_to_global_settings"
down_revision: Union[str, None] = "20251128_null_sess"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add emergency stop flags to global_settings."""
    op.add_column(
        "global_settings",
        sa.Column(
            "emergency_stop_withdrawals",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "global_settings",
        sa.Column(
            "emergency_stop_deposits",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "global_settings",
        sa.Column(
            "emergency_stop_roi",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    """Remove emergency stop flags from global_settings."""
    op.drop_column("global_settings", "emergency_stop_roi")
    op.drop_column("global_settings", "emergency_stop_deposits")
    op.drop_column("global_settings", "emergency_stop_withdrawals")


