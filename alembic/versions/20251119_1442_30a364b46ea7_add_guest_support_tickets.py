"""add_guest_support_tickets

Revision ID: 30a364b46ea7
Revises: 20250119_000001
Create Date: 2025-11-19 14:42:48.564513

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30a364b46ea7'
down_revision: Union[str, None] = '20250119_000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Make user_id nullable to support guest tickets
    op.alter_column(
        'support_tickets',
        'user_id',
        existing_type=sa.Integer(),
        nullable=True,
        existing_nullable=False
    )
    
    # Add telegram_id column for guest tickets
    op.add_column(
        'support_tickets',
        sa.Column('telegram_id', sa.Integer(), nullable=True)
    )
    
    # Create index on telegram_id for guest tickets lookup
    op.create_index(
        'ix_support_tickets_telegram_id',
        'support_tickets',
        ['telegram_id']
    )


def downgrade() -> None:
    """Downgrade database schema."""
    # Drop index
    op.drop_index('ix_support_tickets_telegram_id', table_name='support_tickets')
    
    # Remove telegram_id column
    op.drop_column('support_tickets', 'telegram_id')
    
    # Make user_id non-nullable again (requires data cleanup first)
    # Note: This will fail if there are guest tickets in the database
    op.alter_column(
        'support_tickets',
        'user_id',
        existing_type=sa.Integer(),
        nullable=False,
        existing_nullable=True
    )
