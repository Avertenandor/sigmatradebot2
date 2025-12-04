"""add to_address to transactions

Revision ID: 20250113_000002
Revises: 20251118_000001
Create Date: 2025-01-13 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250113_000002'
down_revision: Union[str, None] = '20251118_000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add to_address column to transactions table
    op.add_column(
        'transactions',
        sa.Column('to_address', sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    # Remove to_address column
    op.drop_column('transactions', 'to_address')

