"""
Transaction model.

Represents all financial transactions in the system.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DECIMAL,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Transaction(Base):
    """Transaction model - all financial operations."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            'amount > 0', name='check_transaction_amount_positive'
        ),
        CheckConstraint(
            'balance_before >= 0',
            name='check_transaction_balance_before_non_negative'
        ),
        CheckConstraint(
            'balance_after >= 0',
            name='check_transaction_balance_after_non_negative'
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

    # Transaction type
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # deposit, withdrawal, referral_reward, deposit_reward, system_payout

    # Amount
    amount: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False
    )
    fee: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), default=Decimal("0"), nullable=False
    )

    # Balance tracking
    balance_before: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False
    )
    balance_after: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )  # pending, confirmed, failed

    # Description
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Reference IDs (optional links to deposits/withdrawals)
    reference_id: Mapped[int | None] = mapped_column(
        nullable=True
    )
    reference_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # deposit, withdrawal, referral, etc.

    # Blockchain data (if applicable)
    tx_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    to_address: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Recipient address (for withdrawals)

    # Timestamps (stored as naive UTC in DB: TIMESTAMP WITHOUT TIME ZONE)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="transactions",
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Transaction(id={self.id}, user_id={self.user_id}, "
            f"type={self.type}, amount={self.amount}, status={self.status})>"
        )
