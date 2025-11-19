"""fix_appeals_user_id_to_integer

Revision ID: d1890f796453
Revises: 15c1a73775fc
Create Date: 2025-11-19 04:48:30.049353

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1890f796453'
down_revision: Union[str, None] = '15c1a73775fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Change user_id from BigInteger to Integer to match users.id type
    # First, drop the foreign key constraint
    op.drop_constraint(
        'appeals_user_id_fkey',
        'appeals',
        type_='foreignkey'
    )
    
    # Change column type from BigInteger to Integer
    op.alter_column(
        'appeals',
        'user_id',
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False
    )
    
    # Recreate foreign key constraint
    op.create_foreign_key(
        'appeals_user_id_fkey',
        'appeals',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Also fix reviewed_by_admin_id to match admins.id type (Integer)
    op.drop_constraint(
        'appeals_reviewed_by_admin_id_fkey',
        'appeals',
        type_='foreignkey'
    )
    
    op.alter_column(
        'appeals',
        'reviewed_by_admin_id',
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True
    )
    
    op.create_foreign_key(
        'appeals_reviewed_by_admin_id_fkey',
        'appeals',
        'admins',
        ['reviewed_by_admin_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade database schema."""
    # Revert user_id back to BigInteger
    op.drop_constraint(
        'appeals_user_id_fkey',
        'appeals',
        type_='foreignkey'
    )
    
    op.alter_column(
        'appeals',
        'user_id',
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False
    )
    
    op.create_foreign_key(
        'appeals_user_id_fkey',
        'appeals',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Revert reviewed_by_admin_id back to BigInteger
    op.drop_constraint(
        'appeals_reviewed_by_admin_id_fkey',
        'appeals',
        type_='foreignkey'
    )
    
    op.alter_column(
        'appeals',
        'reviewed_by_admin_id',
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True
    )
    
    op.create_foreign_key(
        'appeals_reviewed_by_admin_id_fkey',
        'appeals',
        'admins',
        ['reviewed_by_admin_id'],
        ['id'],
        ondelete='SET NULL'
    )
