"""
Add max_open_deposit_level and roi_settings to global_settings

Revision ID: 20251125_140000
Revises: 20251125_130000
Create Date: 2025-11-25 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251125_140000'
down_revision = '20251125_130000'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('global_settings', sa.Column('max_open_deposit_level', sa.Integer(), nullable=False, server_default='5'))
    op.add_column('global_settings', sa.Column('roi_settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'))


def downgrade():
    op.drop_column('global_settings', 'roi_settings')
    op.drop_column('global_settings', 'max_open_deposit_level')

