"""Add service fee to global settings.

Revision ID: 20251130_service_fee
Revises: 20251130_finpass_rl
Create Date: 2025-11-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251130_service_fee'
down_revision = '20251130_finpass_rl'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'global_settings',
        sa.Column('withdrawal_service_fee', sa.Numeric(5, 2), nullable=False, server_default='0.00')
    )


def downgrade() -> None:
    op.drop_column('global_settings', 'withdrawal_service_fee')

