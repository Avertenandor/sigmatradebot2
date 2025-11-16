"""
RewardSession model.

Defines reward rates for different deposit levels and time periods.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.admin import Admin


class RewardSession(Base):
    """
    RewardSession entity.

    Defines reward calculation session:
    - Time-bounded reward periods
    - Level-specific reward rates (1-5)
    - Percentage-based rewards (e.g., 1.1170%)

    Attributes:
        id: Primary key
        name: Session name/description
        reward_rate_level_1: Reward rate for level 1 (%)
        reward_rate_level_2: Reward rate for level 2 (%)
        reward_rate_level_3: Reward rate for level 3 (%)
        reward_rate_level_4: Reward rate for level 4 (%)
        reward_rate_level_5: Reward rate for level 5 (%)
        start_date: Session start timestamp
        end_date: Session end timestamp
        is_active: Active status
        created_by: Admin who created session
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "reward_sessions"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # Session Info
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Reward Rates (percentage, e.g., 1.1170 = 1.117%)
    reward_rate_level_1: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=4), nullable=False
    )
    reward_rate_level_2: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=4), nullable=False
    )
    reward_rate_level_3: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=4), nullable=False
    )
    reward_rate_level_4: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=4), nullable=False
    )
    reward_rate_level_5: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=4), nullable=False
    )

    # Time Period
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )

    # Creator
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admins.id"), nullable=True
    )

    # Relationships
    creator: Mapped[Optional["Admin"]] = relationship(
        "Admin", lazy="joined"
    )

    # Properties

    @property
    def is_currently_active(self) -> bool:
        """Check if session is currently active."""
        if not self.is_active:
            return False

        now = datetime.now(self.start_date.tzinfo)
        return self.start_date <= now <= self.end_date

    @property
    def remaining_days(self) -> int:
        """Get remaining days in session."""
        if not self.is_currently_active:
            return 0

        now = datetime.now(self.end_date.tzinfo)
        remaining = self.end_date - now
        return max(remaining.days, 0)

    def get_reward_rate_for_level(self, level: int) -> Decimal:
        """
        Get reward rate for specific deposit level.

        Args:
            level: Deposit level (1-5)

        Returns:
            Reward rate as Decimal

        Raises:
            ValueError: If level not in range 1-5
        """
        if level < 1 or level > 5:
            raise ValueError(f"Level must be 1-5, got {level}")

        rate_attr = f"reward_rate_level_{level}"
        return getattr(self, rate_attr)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RewardSession(id={self.id}, "
            f"name={self.name!r}, "
            f"is_active={self.is_active})"
        )
