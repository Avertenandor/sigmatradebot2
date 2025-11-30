"""Add fee to transactions.

Revision ID: 20251130_tx_fee
Revises: 20251130_service_fee
Create Date: 2025-11-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251130_tx_fee'
down_revision = '20251130_service_fee'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'transactions',
        sa.Column('fee', sa.Numeric(20, 2), nullable=False, server_default='0.00')
    )


def downgrade() -> None:
    op.drop_column('transactions', 'fee')

