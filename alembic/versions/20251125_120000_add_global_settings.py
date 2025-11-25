"""Add global_settings table

Revision ID: 20251125_120000
Revises: 20251125_100000
Create Date: 2025-11-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251125_120000'
down_revision = '20251125_100000'
branch_labels = None
depends_on = None


def upgrade():
    # Create global_settings table
    op.create_table('global_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('min_withdrawal_amount', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('daily_withdrawal_limit', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('is_daily_limit_enabled', sa.Boolean(), nullable=False),
        sa.Column('auto_withdrawal_enabled', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Initialize with default row
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    
    # Raw SQL to insert default if not exists
    session.execute(sa.text("""
        INSERT INTO global_settings (min_withdrawal_amount, is_daily_limit_enabled, auto_withdrawal_enabled)
        VALUES (5.0, false, true)
    """))
    session.commit()


def downgrade():
    op.drop_table('global_settings')

