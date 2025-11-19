"""create user_notification_settings

Revision ID: 20250119_000001
Revises: d1890f796453
Create Date: 2025-01-19 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250119_000001'
down_revision: Union[str, None] = 'd1890f796453'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create user_notification_settings table
    op.create_table(
        'user_notification_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('deposit_notifications', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('withdrawal_notifications', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('marketing_notifications', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # Create index on user_id
    op.create_index(
        'ix_user_notification_settings_user_id',
        'user_notification_settings',
        ['user_id']
    )


def downgrade() -> None:
    """Downgrade database schema."""
    # Drop index
    op.drop_index('ix_user_notification_settings_user_id', table_name='user_notification_settings')
    
    # Drop table
    op.drop_table('user_notification_settings')

