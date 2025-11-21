"""
Deposit Amount Discrepancy model (R12-3).

Logs discrepancies between expected and received deposit amounts.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.deposit import Deposit
    from app.models.user import User


class DepositAmountDiscrepancy(Base):
    """
    Deposit amount discrepancy log.

    Tracks discrepancies between expected and received deposit amounts
    for audit and reconciliation purposes.
    """

    __tablename__ = "deposit_amount_discrepancies"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Deposit reference
    deposit_id: Mapped[int] = mapped_column(
        ForeignKey("deposits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # User reference
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Expected vs actual
    expected_amount: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False
    )
    actual_amount: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False
    )
    discrepancy: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False
    )
    discrepancy_percent: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False
    )

    # Expected level
    expected_level: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    # Discrepancy type
    discrepancy_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # overpayment, underpayment, between_levels

    # Resolution
    resolution: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # upgraded_level, bonus_balance, partial_deposit, rejected

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    deposit: Mapped["Deposit"] = relationship(
        "Deposit", lazy="joined"
    )
    user: Mapped["User"] = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"DepositAmountDiscrepancy(id={self.id}, "
            f"deposit_id={self.deposit_id}, "
            f"type={self.discrepancy_type}, "
            f"discrepancy={self.discrepancy})"
        )



