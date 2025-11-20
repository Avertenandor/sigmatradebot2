"""cleanup user is_admin

Revision ID: 20251120_072315
Revises: 30a364b46ea7
Create Date: 2025-11-20 07:23:15.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251120_072315'
down_revision = '30a364b46ea7'  # add_guest_support_tickets
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Cleanup user.is_admin field.
    
    Python bot uses Admin table as the only source of truth for admin rights.
    This migration resets all user.is_admin flags to False to ensure consistency.
    The field remains in the schema for backward compatibility but is not used.
    """
    # Reset all is_admin flags to False
    # Admin rights are now determined solely by the Admin table
    op.execute("""
        UPDATE users 
        SET is_admin = FALSE
        WHERE is_admin = TRUE
    """)
    
    # Add comment to column indicating it's not used by Python bot
    op.execute("""
        COMMENT ON COLUMN users.is_admin IS 
        'Deprecated: Admin rights are determined by Admin table only. This field is kept for backward compatibility but not used by Python bot.'
    """)


def downgrade() -> None:
    """
    Revert cleanup (cannot restore original values, but can remove comment).
    """
    # Remove comment
    op.execute("""
        COMMENT ON COLUMN users.is_admin IS NULL
    """)
    # Note: Cannot restore original is_admin values as they were lost
    # This is intentional - Admin table is the authoritative source

