"""
Deposit model.

Represents user deposits into the platform.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DECIMAL,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.deposit_level_version import DepositLevelVersion
    from app.models.user import User


class Deposit(Base):
    """Deposit model - user deposits."""

    __tablename__ = "deposits"
    __table_args__ = (
        CheckConstraint(
            'level >= 1 AND level <= 5',
            name='check_deposit_level_range'
        ),
        CheckConstraint(
            'amount > 0', name='check_deposit_amount_positive'
        ),
        CheckConstraint(
            'roi_cap_amount >= 0',
            name='check_deposit_roi_cap_non_negative'
        ),
        CheckConstraint(
            'roi_paid_amount >= 0',
            name='check_deposit_roi_paid_non_negative'
        ),
        CheckConstraint(
            'roi_paid_amount <= roi_cap_amount',
            name='check_deposit_roi_paid_not_exceeds_cap'
        ),
    )

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # User reference
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Deposit details
    level: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )  # 1-5
    amount: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False
    )

    # Blockchain data
    tx_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    block_number: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    wallet_address: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )  # pending, confirmed, failed, pending_network_recovery (R11-2)

    # R17-1: Deposit version reference
    deposit_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("deposit_level_versions.id"), nullable=True, index=True
    )

    # ROI tracking
    roi_cap_amount: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False, default=Decimal("0")
    )
    roi_paid_amount: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False, default=Decimal("0")
    )
    is_roi_completed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # R12-1: Timestamp when ROI was completed
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Next accrual timestamp for individual reward calculation
    next_accrual_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="deposits",
    )
    deposit_version: Mapped["DepositLevelVersion | None"] = relationship(
        "DepositLevelVersion",
        back_populates="deposits",
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Deposit(id={self.id}, user_id={self.user_id}, "
            f"level={self.level}, amount={self.amount}, status={self.status})>"
        )
