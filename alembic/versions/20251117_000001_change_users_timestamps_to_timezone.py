"""change users timestamps to timezone aware

Revision ID: 20251117_000001
Revises: 
Create Date: 2025-11-17 21:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251117_000001'
down_revision = 'add_finpass_reason'  # add_financial_recovery_reason
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change created_at and updated_at to TIMESTAMP WITH TIME ZONE
    op.alter_column('users', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=False)
    op.alter_column('users', 'updated_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=False)


def downgrade() -> None:
    # Revert to TIMESTAMP WITHOUT TIME ZONE
    op.alter_column('users', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False)
    op.alter_column('users', 'updated_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False)

