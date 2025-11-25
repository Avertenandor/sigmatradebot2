"""Add blockchain settings to global_settings

Revision ID: 20251125_130000
Revises: 20251125_120000
Create Date: 2025-11-25 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251125_130000'
down_revision = '20251125_120000'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('global_settings', sa.Column('active_rpc_provider', sa.String(length=20), nullable=False, server_default='quicknode'))
    op.add_column('global_settings', sa.Column('is_auto_switch_enabled', sa.Boolean(), nullable=False, server_default='true'))


def downgrade():
    op.drop_column('global_settings', 'is_auto_switch_enabled')
    op.drop_column('global_settings', 'active_rpc_provider')

