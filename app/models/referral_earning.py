"""
ReferralEarning model.

Tracks individual referral earnings for payment.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DECIMAL,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.referral import Referral
    from app.models.transaction import Transaction


class ReferralEarning(Base):
    """
    ReferralEarning entity.

    Tracks individual referral earnings:
    - Earnings from referral relationships
    - Payment tracking
    - Source transaction linkage

    Attributes:
        id: Primary key
        referral_id: Foreign key to Referral
        amount: Earning amount
        source_transaction_id: Source transaction (optional)
        tx_hash: Blockchain transaction hash for payment
        paid: Payment status
        created_at: Earning creation timestamp
    """

    __tablename__ = "referral_earnings"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # Referral relationship
    referral_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("referrals.id"), nullable=False, index=True
    )

    # Amount
    amount: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False
    )

    # Source transaction (optional)
    source_transaction_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("transactions.id"), nullable=True
    )

    # Payment tracking
    tx_hash: Mapped[str | None] = mapped_column(
        String(66), nullable=True
    )
    paid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    referral: Mapped["Referral"] = relationship(
        "Referral", lazy="joined"
    )
    source_transaction: Mapped[Optional["Transaction"]] = relationship(
        "Transaction", lazy="joined"
    )

    # Properties

    @property
    def amount_as_number(self) -> float:
        """Get amount as float."""
        return float(self.amount)

    @property
    def is_paid(self) -> bool:
        """Check if earning is paid."""
        return self.paid

    @property
    def is_pending(self) -> bool:
        """Check if earning is pending payment."""
        return not self.paid

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"ReferralEarning(id={self.id}, "
            f"referral_id={self.referral_id}, "
            f"amount={self.amount}, "
            f"paid={self.paid})"
        )


# Composite indexes
Index(
    "idx_referral_earning_referral_paid",
    ReferralEarning.referral_id,
    ReferralEarning.paid,
)
Index(
    "idx_referral_earning_paid_created",
    ReferralEarning.paid,
    ReferralEarning.created_at,
)
