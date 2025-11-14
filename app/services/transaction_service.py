"""
Transaction service.

Provides unified transaction history across all types.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deposit import Deposit
from app.models.enums import TransactionStatus, TransactionType
from app.models.referral_earning import ReferralEarning
from app.models.transaction import Transaction
from app.repositories.deposit_repository import DepositRepository
from app.repositories.referral_earning_repository import (
    ReferralEarningRepository,
)
from app.repositories.transaction_repository import TransactionRepository


@dataclass
class UnifiedTransaction:
    """Unified transaction for display across all types."""

    id: str  # Composite ID: "type:id"
    type: TransactionType
    amount: Decimal
    status: TransactionStatus
    created_at: datetime
    description: str
    tx_hash: Optional[str] = None
    explorer_link: Optional[str] = None
    level: Optional[int] = None  # For deposits
    referral_level: Optional[int] = None  # For referral rewards


class TransactionService:
    """Transaction service for unified transaction history."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize transaction service."""
        self.session = session
        self.transaction_repo = TransactionRepository(session)
        self.deposit_repo = DepositRepository(session)
        self.earning_repo = ReferralEarningRepository(session)

    async def get_all_transactions(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        transaction_type: Optional[TransactionType] = None,
        status: Optional[TransactionStatus] = None,
    ) -> dict:
        """
        Get all transactions for user (deposits, withdrawals, earnings).

        Combines deposits, withdrawals, and referral earnings into one list.

        Args:
            user_id: User ID
            limit: Max transactions to return
            offset: Offset for pagination
            transaction_type: Filter by type (optional)
            status: Filter by status (optional)

        Returns:
            Dict with transactions, total, has_more
        """
        all_transactions: list[UnifiedTransaction] = []

        # 1. Get deposits
        if not transaction_type or transaction_type == TransactionType.DEPOSIT:
            deposits = await self._get_deposits(user_id, status)
            all_transactions.extend(deposits)

        # 2. Get withdrawals
        if (
            not transaction_type
            or transaction_type == TransactionType.WITHDRAWAL
        ):
            withdrawals = await self._get_withdrawals(user_id, status)
            all_transactions.extend(withdrawals)

        # 3. Get referral earnings
        if (
            not transaction_type
            or transaction_type == TransactionType.REFERRAL_REWARD
        ):
            earnings = await self._get_referral_earnings(user_id)
            all_transactions.extend(earnings)

        # Sort by date (newest first)
        all_transactions.sort(
            key=lambda t: t.created_at, reverse=True
        )

        # Pagination
        total = len(all_transactions)
        paginated = all_transactions[offset : offset + limit]
        has_more = offset + limit < total

        logger.debug(
            "Retrieved all transactions",
            extra={
                "user_id": user_id,
                "total": total,
                "returned": len(paginated),
                "has_more": has_more,
            },
        )

        return {
            "transactions": paginated,
            "total": total,
            "has_more": has_more,
        }

    async def _get_deposits(
        self, user_id: int, status_filter: Optional[TransactionStatus]
    ) -> list[UnifiedTransaction]:
        """Get deposits as unified transactions."""
        stmt = select(Deposit).where(Deposit.user_id == user_id)

        if status_filter:
            stmt = stmt.where(Deposit.status == status_filter.value)

        result = await self.session.execute(stmt)
        deposits = result.scalars().all()

        unified = []
        for deposit in deposits:
            tx_hash = deposit.tx_hash
            unified.append(
                UnifiedTransaction(
                    id=f"deposit:{deposit.id}",
                    type=TransactionType.DEPOSIT,
                    amount=deposit.amount,
                    status=TransactionStatus(deposit.status),
                    created_at=deposit.created_at,
                    description=f"Депозит уровня {deposit.level}",
                    tx_hash=tx_hash,
                    explorer_link=(
                        f"https://bscscan.com/tx/{tx_hash}"
                        if tx_hash else None
                    ),
                    level=deposit.level,
                )
            )

        return unified

    async def _get_withdrawals(
        self, user_id: int, status_filter: Optional[TransactionStatus]
    ) -> list[UnifiedTransaction]:
        """Get withdrawals as unified transactions."""
        stmt = select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.WITHDRAWAL.value,
        )

        if status_filter:
            stmt = stmt.where(Transaction.status == status_filter.value)

        result = await self.session.execute(stmt)
        withdrawals = result.scalars().all()

        unified = []
        for withdrawal in withdrawals:
            tx_hash = withdrawal.tx_hash
            unified.append(
                UnifiedTransaction(
                    id=f"withdrawal:{withdrawal.id}",
                    type=TransactionType.WITHDRAWAL,
                    amount=withdrawal.amount,
                    status=TransactionStatus(withdrawal.status),
                    created_at=withdrawal.created_at,
                    description="Вывод средств",
                    tx_hash=tx_hash,
                    explorer_link=(
                        f"https://bscscan.com/tx/{tx_hash}"
                        if tx_hash else None
                    ),
                )
            )

        return unified

    async def _get_referral_earnings(
        self, user_id: int
    ) -> list[UnifiedTransaction]:
        """Get referral earnings as unified transactions."""
        # Get earnings through referral relationships
        earnings = await self.earning_repo.get_all_for_referrer(user_id)

        unified = []
        for earning in earnings:
            status = (
                TransactionStatus.CONFIRMED
                if earning.paid
                else TransactionStatus.PENDING
            )

            # Get referral level from relationship
            referral = earning.referral
            level = referral.level if referral else None

            unified.append(
                UnifiedTransaction(
                    id=f"referral:{earning.id}",
                    type=TransactionType.REFERRAL_REWARD,
                    amount=earning.amount,
                    status=status,
                    created_at=earning.created_at,
                    description=(
                        f"Реферальное вознаграждение "
                        f"(уровень {level or '?'})"
                    ),
                    tx_hash=earning.tx_hash,
                    referral_level=level,
                )
            )

        return unified

    async def get_transaction_stats(
        self, user_id: int
    ) -> dict:
        """
        Get transaction statistics for user.

        Args:
            user_id: User ID

        Returns:
            Dict with comprehensive transaction stats
        """
        # Get deposits
        deposits_stmt = select(Deposit).where(
            Deposit.user_id == user_id,
            Deposit.status == TransactionStatus.CONFIRMED.value,
        )
        deposits_result = await self.session.execute(deposits_stmt)
        deposits = list(deposits_result.scalars().all())
        total_deposits = sum(d.amount for d in deposits)

        # Get withdrawals
        withdrawals_stmt = select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.WITHDRAWAL.value,
        )
        withdrawals_result = await self.session.execute(withdrawals_stmt)
        withdrawals = list(withdrawals_result.scalars().all())

        confirmed_withdrawals = [
            w for w in withdrawals
            if w.status == TransactionStatus.CONFIRMED.value
        ]
        pending_withdrawals = [
            w for w in withdrawals
            if w.status == TransactionStatus.PENDING.value
        ]

        total_withdrawals = sum(w.amount for w in confirmed_withdrawals)
        pending_withdrawals_amount = sum(
            w.amount for w in pending_withdrawals
        )

        # Get referral earnings
        earnings = await self.earning_repo.get_all_for_referrer(user_id)
        total_referral_earnings = sum(e.amount for e in earnings)
        pending_earnings = sum(
            e.amount for e in earnings if not e.paid
        )

        return {
            "total_deposits": total_deposits,
            "total_withdrawals": total_withdrawals,
            "total_referral_earnings": total_referral_earnings,
            "pending_withdrawals": pending_withdrawals_amount,
            "pending_earnings": pending_earnings,
            "transaction_count": {
                "deposits": len(deposits),
                "withdrawals": len(confirmed_withdrawals),
                "referral_rewards": len([e for e in earnings if e.paid]),
            },
        }

    async def get_recent_transactions(
        self, user_id: int, limit: int = 5
    ) -> list[UnifiedTransaction]:
        """
        Get recent transactions for user.

        Args:
            user_id: User ID
            limit: Max transactions to return

        Returns:
            List of recent unified transactions
        """
        result = await self.get_all_transactions(
            user_id, limit=limit, offset=0
        )
        return result["transactions"]
