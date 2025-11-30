"""Add finpass rate limiting fields to users.

Revision ID: 20251130_finpass_rl
Revises: 20251129_000001_add_emergency_stops_to_global_settings
Create Date: 2025-11-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251130_finpass_rl'
down_revision = '20251129_add_emergency_stops_to_global_settings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add finpass_attempts column
    op.add_column(
        'users',
        sa.Column('finpass_attempts', sa.Integer(), nullable=False, server_default='0')
    )
    # Add finpass_locked_until column
    op.add_column(
        'users',
        sa.Column('finpass_locked_until', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('users', 'finpass_locked_until')
    op.drop_column('users', 'finpass_attempts')

