"""Add roi_notifications to user_notification_settings.

Revision ID: 20251130_roi_notif
Revises: 20251130_tx_fee
Create Date: 2025-11-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251130_roi_notif'
down_revision = '20251130_tx_fee'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'user_notification_settings',
        sa.Column('roi_notifications', sa.Boolean(), nullable=False, server_default='true')
    )


def downgrade() -> None:
    op.drop_column('user_notification_settings', 'roi_notifications')

