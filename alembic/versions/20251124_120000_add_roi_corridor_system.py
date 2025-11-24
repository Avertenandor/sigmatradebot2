"""Add ROI corridor system.

Revision ID: 20251124_120000
Revises: 20251123_063656
Create Date: 2025-11-24 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20251124_120000"
down_revision = "20251123_063656"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema."""
    # 1. Create deposit_corridor_history table
    op.create_table(
        "deposit_corridor_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("roi_min", sa.DECIMAL(5, 2), nullable=True),
        sa.Column("roi_max", sa.DECIMAL(5, 2), nullable=True),
        sa.Column("roi_fixed", sa.DECIMAL(5, 2), nullable=True),
        sa.Column("changed_by_admin_id", sa.Integer(), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("applies_to", sa.String(20), nullable=False),
    )
    
    # Create indexes
    op.create_index(
        "idx_corridor_history_level_changed_at",
        "deposit_corridor_history",
        ["level", "changed_at"],
    )
    
    # Create foreign key
    op.create_foreign_key(
        "fk_corridor_history_admin",
        "deposit_corridor_history",
        "admins",
        ["changed_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )
    
    # 2. Add actual_rate column to deposit_rewards
    op.add_column(
        "deposit_rewards",
        sa.Column("actual_rate", sa.DECIMAL(5, 2), nullable=True),
    )
    
    # 3. Add next_accrual_at column to deposits
    op.add_column(
        "deposits",
        sa.Column("next_accrual_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # Create index for next_accrual_at
    op.create_index(
        "idx_deposits_next_accrual_at",
        "deposits",
        ["next_accrual_at"],
        postgresql_where=sa.text("next_accrual_at IS NOT NULL"),
    )
    
    # 4. Initialize SystemSettings for ROI corridors
    # This will be done via SQL to ensure it works in migration
    op.execute(
        """
        INSERT INTO system_settings (key, value, updated_at)
        VALUES
            ('REWARD_ACCRUAL_PERIOD_HOURS', '6', CURRENT_TIMESTAMP),
            ('LEVEL_1_ROI_MODE', 'custom', CURRENT_TIMESTAMP),
            ('LEVEL_1_ROI_MIN', '0.8', CURRENT_TIMESTAMP),
            ('LEVEL_1_ROI_MAX', '10.0', CURRENT_TIMESTAMP),
            ('LEVEL_1_ROI_FIXED', '5.0', CURRENT_TIMESTAMP),
            ('LEVEL_2_ROI_MODE', 'custom', CURRENT_TIMESTAMP),
            ('LEVEL_2_ROI_MIN', '1.0', CURRENT_TIMESTAMP),
            ('LEVEL_2_ROI_MAX', '12.0', CURRENT_TIMESTAMP),
            ('LEVEL_2_ROI_FIXED', '6.0', CURRENT_TIMESTAMP),
            ('LEVEL_3_ROI_MODE', 'custom', CURRENT_TIMESTAMP),
            ('LEVEL_3_ROI_MIN', '1.2', CURRENT_TIMESTAMP),
            ('LEVEL_3_ROI_MAX', '15.0', CURRENT_TIMESTAMP),
            ('LEVEL_3_ROI_FIXED', '7.0', CURRENT_TIMESTAMP),
            ('LEVEL_4_ROI_MODE', 'custom', CURRENT_TIMESTAMP),
            ('LEVEL_4_ROI_MIN', '1.5', CURRENT_TIMESTAMP),
            ('LEVEL_4_ROI_MAX', '18.0', CURRENT_TIMESTAMP),
            ('LEVEL_4_ROI_FIXED', '8.0', CURRENT_TIMESTAMP),
            ('LEVEL_5_ROI_MODE', 'custom', CURRENT_TIMESTAMP),
            ('LEVEL_5_ROI_MIN', '2.0', CURRENT_TIMESTAMP),
            ('LEVEL_5_ROI_MAX', '20.0', CURRENT_TIMESTAMP),
            ('LEVEL_5_ROI_FIXED', '10.0', CURRENT_TIMESTAMP)
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    """Downgrade database schema."""
    # Remove indexes
    op.drop_index("idx_deposits_next_accrual_at", "deposits")
    op.drop_index("idx_corridor_history_level_changed_at", "deposit_corridor_history")
    
    # Remove columns
    op.drop_column("deposits", "next_accrual_at")
    op.drop_column("deposit_rewards", "actual_rate")
    
    # Drop table
    op.drop_table("deposit_corridor_history")
    
    # Remove system settings
    op.execute(
        """
        DELETE FROM system_settings
        WHERE key LIKE 'LEVEL_%_ROI_%' OR key = 'REWARD_ACCRUAL_PERIOD_HOURS'
        """
    )

