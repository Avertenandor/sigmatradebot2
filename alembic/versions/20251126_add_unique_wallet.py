"""Add unique constraint to users.wallet_address.

Revision ID: 20251126_add_unique_wallet
Revises: 20251125_140000_add_roi_settings
Create Date: 2025-11-26 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251126_add_unique_wallet'
down_revision: Union[str, None] = '20251125_140000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create unique index on wallet_address (case-insensitive if possible, but standard unique is simpler)
    # Standard unique constraint
    op.create_unique_constraint('uq_users_wallet_address', 'users', ['wallet_address'])


def downgrade() -> None:
    op.drop_constraint('uq_users_wallet_address', 'users', type_='unique')

