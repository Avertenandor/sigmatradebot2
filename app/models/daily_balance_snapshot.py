"""
Daily Balance Snapshot model (R10-2).

Stores daily balance snapshots for financial reconciliation.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, Date, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

if TYPE_CHECKING:
    pass


class DailyBalanceSnapshot(Base):
    """
    Daily balance snapshot for reconciliation tracking.

    Stores daily snapshots of system balances for audit and reconciliation.
    """

    __tablename__ = "daily_balance_snapshots"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Snapshot date
    snapshot_date: Mapped[date] = mapped_column(
        Date, nullable=False, unique=True, index=True
    )

    # Deposits
    total_deposits: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False, default=Decimal("0")
    )

    # Withdrawals
    total_withdrawals: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False, default=Decimal("0")
    )

    # Referral earnings
    total_paid_referral_earnings: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False, default=Decimal("0")
    )

    # User balances
    total_user_balances: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False, default=Decimal("0")
    )
    total_pending_earnings: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False, default=Decimal("0")
    )
    total_pending_withdrawals: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False, default=Decimal("0")
    )

    # Calculated values
    expected_balance: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False, default=Decimal("0")
    )
    actual_balance: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False, default=Decimal("0")
    )
    discrepancy: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False, default=Decimal("0")
    )
    discrepancy_percent: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False, default=Decimal("0")
    )

    # Status
    reconciliation_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending"
    )  # pending, reconciled, discrepancy

    # Report (JSON stored as text)
    reconciliation_report: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"DailyBalanceSnapshot(id={self.id}, "
            f"date={self.snapshot_date}, "
            f"discrepancy={self.discrepancy})"
        )

