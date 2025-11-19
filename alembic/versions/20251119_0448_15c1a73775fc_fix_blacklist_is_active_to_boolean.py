"""fix_blacklist_is_active_to_boolean

Revision ID: 15c1a73775fc
Revises: 20250118_000001
Create Date: 2025-11-19 04:48:26.199396

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '15c1a73775fc'
down_revision: Union[str, None] = '20250118_000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Convert is_active from Integer (1/0) to Boolean (true/false)
    # PostgreSQL: ALTER COLUMN with USING clause
    op.execute("""
        ALTER TABLE blacklist 
        ALTER COLUMN is_active TYPE BOOLEAN 
        USING CASE WHEN is_active = 1 THEN TRUE ELSE FALSE END
    """)


def downgrade() -> None:
    """Downgrade database schema."""
    # Convert back from Boolean to Integer (1/0)
    op.execute("""
        ALTER TABLE blacklist 
        ALTER COLUMN is_active TYPE INTEGER 
        USING CASE WHEN is_active = TRUE THEN 1 ELSE 0 END
    """)
