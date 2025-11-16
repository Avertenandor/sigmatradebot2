"""
DepositReward model.

Tracks daily ROI rewards for deposits.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.deposit import Deposit
    from app.models.reward_session import RewardSession
    from app.models.user import User


class DepositReward(Base):
    """
    DepositReward entity.

    Tracks daily ROI rewards:
    - Calculated per deposit per reward session
    - Payment tracking
    - Denormalized deposit info for efficiency

    Attributes:
        id: Primary key
        user_id: User receiving reward
        deposit_id: Source deposit
        reward_session_id: Reward calculation session
        deposit_level: Denormalized deposit level (1-5)
        deposit_amount: Denormalized deposit amount
        reward_rate: Applied reward rate (%)
        reward_amount: Calculated reward amount
        paid: Payment status
        paid_at: Payment timestamp
        tx_hash: Blockchain transaction hash
        calculated_at: Reward calculation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "deposit_rewards"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # References
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    deposit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("deposits.id"), nullable=False, index=True
    )
    reward_session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reward_sessions.id"),
        nullable=False,
        index=True,
    )

    # Denormalized data (for efficiency)
    deposit_level: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    deposit_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False
    )

    # Reward calculation
    reward_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=4), nullable=False
    )
    reward_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False
    )

    # Payment tracking
    paid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tx_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Timestamps
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # updated_at inherited from Base

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="joined")
    deposit: Mapped["Deposit"] = relationship("Deposit", lazy="joined")
    reward_session: Mapped["RewardSession"] = relationship(
        "RewardSession", lazy="joined"
    )

    # Properties

    @property
    def display_reward_amount(self) -> str:
        """Format reward amount for display."""
        return f"{self.reward_amount:.8f}"

    @property
    def display_deposit_amount(self) -> str:
        """Format deposit amount for display."""
        return f"{self.deposit_amount:.8f}"

    @property
    def display_reward_rate(self) -> str:
        """Format reward rate for display."""
        return f"{self.reward_rate:.4f}%"

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"DepositReward(id={self.id}, "
            f"user_id={self.user_id}, "
            f"deposit_id={self.deposit_id}, "
            f"paid={self.paid})"
        )


# Composite indexes
Index(
    "idx_deposit_reward_user_paid",
    DepositReward.user_id,
    DepositReward.paid,
)
Index(
    "idx_deposit_reward_session_paid",
    DepositReward.reward_session_id,
    DepositReward.paid,
)

# Unique constraint: one reward per deposit per session
UniqueConstraint(
    DepositReward.deposit_id,
    DepositReward.reward_session_id,
    name="uq_deposit_reward_deposit_session",
)
