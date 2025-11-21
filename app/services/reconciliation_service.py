"""
Reconciliation Service (R10-2).

Financial reconciliation service for daily balance verification.
"""

import json
from datetime import UTC, date, datetime
from decimal import Decimal

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_balance_snapshot import DailyBalanceSnapshot
from app.models.deposit import Deposit
from app.models.enums import TransactionStatus, TransactionType
from app.models.referral_earning import ReferralEarning
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.base import BaseRepository


class ReconciliationService:
    """Service for financial reconciliation."""

    # Tolerance for reconciliation (5%)
    RECONCILIATION_TOLERANCE = Decimal("0.05")

    def __init__(self, session: AsyncSession) -> None:
        """Initialize reconciliation service."""
        self.session = session

    async def perform_reconciliation(
        self, snapshot_date: date | None = None
    ) -> dict:
        """
        Perform financial reconciliation.

        Formula:
        Expected = SUM(confirmed_deposits) - SUM(confirmed_withdrawals)
                  - SUM(paid_referral_earnings)
        Actual = SUM(users.balance) + SUM(users.pending_earnings)
                + SUM(pending_withdrawals.amount)

        Args:
            snapshot_date: Date for snapshot (default: today)

        Returns:
            Dict with reconciliation results
        """
        if snapshot_date is None:
            snapshot_date = date.today()

        logger.info(f"Starting reconciliation for {snapshot_date}")

        try:
            # Calculate expected balance
            expected = await self._calculate_expected_balance()

            # Calculate actual balance
            actual = await self._calculate_actual_balance()

            # Calculate discrepancy
            discrepancy = actual - expected
            discrepancy_percent = (
                (discrepancy / expected * 100) if expected > 0 else Decimal("0")
            )

            # Check if within tolerance (5%)
            within_tolerance = abs(discrepancy_percent) <= (
                self.RECONCILIATION_TOLERANCE * 100
            )

            # Get detailed breakdown
            breakdown = await self._get_breakdown()

            # Create snapshot
            snapshot = await self._create_snapshot(
                snapshot_date=snapshot_date,
                expected=expected,
                actual=actual,
                discrepancy=discrepancy,
                discrepancy_percent=discrepancy_percent,
                breakdown=breakdown,
                within_tolerance=within_tolerance,
            )

            await self.session.commit()

            result = {
                "success": True,
                "snapshot_id": snapshot.id,
                "snapshot_date": snapshot_date.isoformat(),
                "expected_balance": float(expected),
                "actual_balance": float(actual),
                "discrepancy": float(discrepancy),
                "discrepancy_percent": float(discrepancy_percent),
                "within_tolerance": within_tolerance,
                "status": snapshot.reconciliation_status,
                "breakdown": breakdown,
            }

            # If discrepancy > 5%, mark as critical
            if not within_tolerance:
                result["critical"] = True
                logger.error(
                    f"CRITICAL: Reconciliation discrepancy detected: "
                    f"{discrepancy_percent:.2f}% "
                    f"({discrepancy} USDT)",
                    extra={
                        "snapshot_id": snapshot.id,
                        "expected": float(expected),
                        "actual": float(actual),
                        "discrepancy": float(discrepancy),
                    },
                )

            return result

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Reconciliation failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def _calculate_expected_balance(self) -> Decimal:
        """
        Calculate expected system balance.

        Expected = SUM(confirmed_deposits) - SUM(confirmed_withdrawals)
                  - SUM(paid_referral_earnings)

        Returns:
            Expected balance
        """
        # Sum confirmed deposits
        deposits_stmt = select(func.sum(Deposit.amount)).where(
            Deposit.status == TransactionStatus.CONFIRMED.value
        )
        deposits_result = await self.session.execute(deposits_stmt)
        total_deposits = deposits_result.scalar() or Decimal("0")

        # Sum confirmed withdrawals
        withdrawals_stmt = (
            select(func.sum(Transaction.amount))
            .where(
                Transaction.type == TransactionType.WITHDRAWAL.value,
                Transaction.status == TransactionStatus.CONFIRMED.value,
            )
        )
        withdrawals_result = await self.session.execute(withdrawals_stmt)
        total_withdrawals = withdrawals_result.scalar() or Decimal("0")

        # Sum paid referral earnings
        referral_earnings_stmt = select(func.sum(ReferralEarning.amount)).where(
            ReferralEarning.paid == True  # noqa: E712
        )
        referral_result = await self.session.execute(referral_earnings_stmt)
        total_paid_referral = referral_result.scalar() or Decimal("0")

        # Calculate expected
        expected = total_deposits - total_withdrawals - total_paid_referral

        logger.debug(
            f"Expected balance calculation: "
            f"deposits={total_deposits}, "
            f"withdrawals={total_withdrawals}, "
            f"paid_referral={total_paid_referral}, "
            f"expected={expected}"
        )

        return expected

    async def _calculate_actual_balance(self) -> Decimal:
        """
        Calculate actual system balance.

        Actual = SUM(users.balance) + SUM(users.pending_earnings)
                + SUM(pending_withdrawals.amount)

        Returns:
            Actual balance
        """
        # Sum user balances
        user_balance_stmt = select(func.sum(User.balance))
        user_balance_result = await self.session.execute(user_balance_stmt)
        total_user_balances = user_balance_result.scalar() or Decimal("0")

        # Sum pending earnings
        pending_earnings_stmt = select(func.sum(User.pending_earnings))
        pending_earnings_result = await self.session.execute(
            pending_earnings_stmt
        )
        total_pending_earnings = (
            pending_earnings_result.scalar() or Decimal("0")
        )

        # Sum pending withdrawals
        pending_withdrawals_stmt = (
            select(func.sum(Transaction.amount))
            .where(
                Transaction.type == TransactionType.WITHDRAWAL.value,
                Transaction.status.in_(
                    [
                        TransactionStatus.PENDING.value,
                        TransactionStatus.PROCESSING.value,
                    ]
                ),
            )
        )
        pending_withdrawals_result = await self.session.execute(
            pending_withdrawals_stmt
        )
        total_pending_withdrawals = (
            pending_withdrawals_result.scalar() or Decimal("0")
        )

        # Calculate actual
        actual = (
            total_user_balances
            + total_pending_earnings
            + total_pending_withdrawals
        )

        logger.debug(
            f"Actual balance calculation: "
            f"user_balances={total_user_balances}, "
            f"pending_earnings={total_pending_earnings}, "
            f"pending_withdrawals={total_pending_withdrawals}, "
            f"actual={actual}"
        )

        return actual

    async def _get_breakdown(self) -> dict:
        """
        Get detailed breakdown of reconciliation components.

        Returns:
            Dict with detailed breakdown
        """
        # Get deposit breakdown
        deposits_stmt = select(
            func.count(Deposit.id),
            func.sum(Deposit.amount),
        ).where(Deposit.status == TransactionStatus.CONFIRMED.value)
        deposits_result = await self.session.execute(deposits_stmt)
        deposits_row = deposits_result.first()
        deposit_count = deposits_row[0] or 0
        deposit_total = deposits_row[1] or Decimal("0")

        # Get withdrawal breakdown
        withdrawals_stmt = select(
            func.count(Transaction.id),
            func.sum(Transaction.amount),
        ).where(
            Transaction.type == TransactionType.WITHDRAWAL.value,
            Transaction.status == TransactionStatus.CONFIRMED.value,
        )
        withdrawals_result = await self.session.execute(withdrawals_stmt)
        withdrawals_row = withdrawals_result.first()
        withdrawal_count = withdrawals_row[0] or 0
        withdrawal_total = withdrawals_row[1] or Decimal("0")

        # Get referral earnings breakdown
        referral_stmt = select(
            func.count(ReferralEarning.id),
            func.sum(ReferralEarning.amount),
        ).where(ReferralEarning.paid == True)  # noqa: E712
        referral_result = await self.session.execute(referral_stmt)
        referral_row = referral_result.first()
        referral_count = referral_row[0] or 0
        referral_total = referral_row[1] or Decimal("0")

        # Get user balance breakdown
        user_balance_stmt = select(
            func.count(User.id),
            func.sum(User.balance),
            func.sum(User.pending_earnings),
        )
        user_balance_result = await self.session.execute(user_balance_stmt)
        user_balance_row = user_balance_result.first()
        user_count = user_balance_row[0] or 0
        total_user_balance = user_balance_row[1] or Decimal("0")
        total_pending_earnings = user_balance_row[2] or Decimal("0")

        # Get pending withdrawals breakdown
        pending_withdrawals_stmt = select(
            func.count(Transaction.id),
            func.sum(Transaction.amount),
        ).where(
            Transaction.type == TransactionType.WITHDRAWAL.value,
            Transaction.status.in_(
                [
                    TransactionStatus.PENDING.value,
                    TransactionStatus.PROCESSING.value,
                ]
            ),
        )
        pending_withdrawals_result = await self.session.execute(
            pending_withdrawals_stmt
        )
        pending_withdrawals_row = pending_withdrawals_result.first()
        pending_withdrawal_count = pending_withdrawals_row[0] or 0
        pending_withdrawal_total = (
            pending_withdrawals_row[1] or Decimal("0")
        )

        return {
            "deposits": {
                "count": deposit_count,
                "total": float(deposit_total),
            },
            "withdrawals": {
                "count": withdrawal_count,
                "total": float(withdrawal_total),
            },
            "paid_referral_earnings": {
                "count": referral_count,
                "total": float(referral_total),
            },
            "user_balances": {
                "user_count": user_count,
                "total_balance": float(total_user_balance),
                "total_pending_earnings": float(total_pending_earnings),
            },
            "pending_withdrawals": {
                "count": pending_withdrawal_count,
                "total": float(pending_withdrawal_total),
            },
        }

    async def _create_snapshot(
        self,
        snapshot_date: date,
        expected: Decimal,
        actual: Decimal,
        discrepancy: Decimal,
        discrepancy_percent: Decimal,
        breakdown: dict,
        within_tolerance: bool,
    ) -> DailyBalanceSnapshot:
        """
        Create daily balance snapshot.

        Args:
            snapshot_date: Snapshot date
            expected: Expected balance
            actual: Actual balance
            discrepancy: Discrepancy amount
            discrepancy_percent: Discrepancy percentage
            breakdown: Detailed breakdown
            within_tolerance: Whether within tolerance

        Returns:
            Created snapshot
        """
        # Determine status
        if within_tolerance:
            status = "reconciled"
        elif abs(discrepancy_percent) <= (self.RECONCILIATION_TOLERANCE * 100):
            status = "reconciled"
        else:
            status = "discrepancy"

        # Create report
        report = {
            "breakdown": breakdown,
            "expected": float(expected),
            "actual": float(actual),
            "discrepancy": float(discrepancy),
            "discrepancy_percent": float(discrepancy_percent),
            "within_tolerance": within_tolerance,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Check if snapshot already exists for this date
        existing_stmt = select(DailyBalanceSnapshot).where(
            DailyBalanceSnapshot.snapshot_date == snapshot_date
        )
        existing_result = await self.session.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        if existing:
            # Update existing snapshot
            existing.total_deposits = Decimal(str(breakdown["deposits"]["total"]))
            existing.total_withdrawals = Decimal(str(breakdown["withdrawals"]["total"]))
            existing.total_paid_referral_earnings = Decimal(
                str(breakdown["paid_referral_earnings"]["total"])
            )
            existing.total_user_balances = Decimal(
                str(breakdown["user_balances"]["total_balance"])
            )
            existing.total_pending_earnings = Decimal(
                str(breakdown["user_balances"]["total_pending_earnings"])
            )
            existing.total_pending_withdrawals = Decimal(
                str(breakdown["pending_withdrawals"]["total"])
            )
            existing.expected_balance = expected
            existing.actual_balance = actual
            existing.discrepancy = discrepancy
            existing.discrepancy_percent = discrepancy_percent
            existing.reconciliation_status = status
            existing.reconciliation_report = json.dumps(report, indent=2)

            logger.info(f"Updated snapshot for {snapshot_date}")
            return existing
        else:
            # Create new snapshot
            snapshot = DailyBalanceSnapshot(
                snapshot_date=snapshot_date,
                total_deposits=Decimal(str(breakdown["deposits"]["total"])),
                total_withdrawals=Decimal(str(breakdown["withdrawals"]["total"])),
                total_paid_referral_earnings=Decimal(
                    str(breakdown["paid_referral_earnings"]["total"])
                ),
                total_user_balances=Decimal(
                    str(breakdown["user_balances"]["total_balance"])
                ),
                total_pending_earnings=Decimal(
                    str(breakdown["user_balances"]["total_pending_earnings"])
                ),
                total_pending_withdrawals=Decimal(
                    str(breakdown["pending_withdrawals"]["total"])
                ),
                expected_balance=expected,
                actual_balance=actual,
                discrepancy=discrepancy,
                discrepancy_percent=discrepancy_percent,
                reconciliation_status=status,
                reconciliation_report=json.dumps(report, indent=2),
            )

            self.session.add(snapshot)
            await self.session.flush()

            logger.info(f"Created snapshot for {snapshot_date}")
            return snapshot

