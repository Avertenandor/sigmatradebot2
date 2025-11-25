"""Add referral_code column

Revision ID: 20251125_100000
Revises: 20251124_180000
Create Date: 2025-11-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import secrets

# revision identifiers, used by Alembic.
revision = '20251125_100000'
down_revision = '20251124_180000'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Add column as nullable first
    op.add_column('users', sa.Column('referral_code', sa.String(length=20), nullable=True))
    op.create_index(op.f('ix_users_referral_code'), 'users', ['referral_code'], unique=True)

    # 2. Generate codes for existing users
    # We need to bind a session to execute updates
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    
    # Reflect User table
    metadata = sa.MetaData()
    user_table = sa.Table('users', metadata, autoload_with=bind)
    
    # Fetch all users
    try:
        users = session.query(user_table).all()
        
        for user in users:
            # Generate unique code
            code = secrets.token_urlsafe(8)
            # Update user
            stmt = user_table.update().where(user_table.c.id == user.id).values(referral_code=code)
            session.execute(stmt)
        
        session.commit()
    except Exception as e:
        print(f"Error updating referral codes: {e}")
        session.rollback()
        raise

    # 3. Make column non-nullable if desired (keeping nullable for safety for now, or altering)
    # op.alter_column('users', 'referral_code', nullable=False)


def downgrade():
    op.drop_index(op.f('ix_users_referral_code'), table_name='users')
    op.drop_column('users', 'referral_code')

