"""Make reward_session_id nullable

Revision ID: 20251128_make_reward_session_id_nullable
Revises: 20251126_add_unique_wallet
Create Date: 2025-11-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251128_null_sess'
down_revision: Union[str, None] = '20251126_add_unique_wallet'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make reward_session_id nullable in deposit_rewards table
    op.alter_column('deposit_rewards', 'reward_session_id',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade() -> None:
    # Revert reward_session_id to non-nullable
    # Note: This might fail if there are records with NULL reward_session_id
    op.alter_column('deposit_rewards', 'reward_session_id',
               existing_type=sa.INTEGER(),
               nullable=False)

