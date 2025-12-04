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
    # Create backup table to store original is_admin values for potential rollback
    op.execute("""
        CREATE TABLE IF NOT EXISTS users_is_admin_backup (
            user_id INTEGER PRIMARY KEY,
            is_admin BOOLEAN NOT NULL,
            backup_created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Save current is_admin values before changing them
    op.execute("""
        INSERT INTO users_is_admin_backup (user_id, is_admin)
        SELECT id, is_admin FROM users WHERE is_admin = TRUE
        ON CONFLICT (user_id) DO NOTHING
    """)

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
    Revert cleanup and restore original is_admin values from backup.
    """
    # Restore is_admin values from backup table
    op.execute("""
        UPDATE users
        SET is_admin = backup.is_admin
        FROM users_is_admin_backup backup
        WHERE users.id = backup.user_id
    """)

    # Drop backup table
    op.execute("""
        DROP TABLE IF EXISTS users_is_admin_backup
    """)

    # Remove comment
    op.execute("""
        COMMENT ON COLUMN users.is_admin IS NULL
    """)

