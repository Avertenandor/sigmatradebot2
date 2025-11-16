"""
PaymentRetry model (КРИТИЧНО - PART5).

Tracks failed payment attempts with retry logic and DLQ.
"""

import enum
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class PaymentType(enum.StrEnum):
    """Payment type enum."""

    REFERRAL_EARNING = "REFERRAL_EARNING"
    DEPOSIT_REWARD = "DEPOSIT_REWARD"


class PaymentRetry(Base):
    """
    PaymentRetry entity (КРИТИЧНО из PART5!).

    Implements payment retry logic with exponential backoff:
    - Tracks failed payment attempts
    - Dead Letter Queue (DLQ) for permanent failures
    - Links to ReferralEarning or DepositReward IDs

    Attributes:
        id: Primary key
        user_id: User receiving payment
        amount: Payment amount
        payment_type: Type of payment
        earning_ids: Array of earning IDs (JSON)
        attempt_count: Number of retry attempts
        max_retries: Maximum retry limit
        last_attempt_at: Last retry timestamp
        next_retry_at: Next scheduled retry
        last_error: Last error message
        error_stack: Full error stack trace
        in_dlq: Dead Letter Queue flag
        resolved: Successfully paid flag
        tx_hash: Blockchain transaction hash
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "payment_retries"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # User
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )

    # Payment details
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=8), nullable=False
    )
    payment_type: Mapped[PaymentType] = mapped_column(
        SQLEnum(PaymentType, native_enum=False),
        nullable=False,
    )

    # Earning IDs (array of numbers stored as JSON)
    earning_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False
    )

    # Retry logic
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Error tracking
    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    error_stack: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Status flags
    in_dlq: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    # Payment result
    tx_hash: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"PaymentRetry(id={self.id}, "
            f"user_id={self.user_id}, "
            f"payment_type={self.payment_type.value}, "
            f"resolved={self.resolved})"
        )


# Critical indexes for PART5
Index(
    "idx_payment_retry_resolved_dlq",
    PaymentRetry.resolved,
    PaymentRetry.in_dlq
)
