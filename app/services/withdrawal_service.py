"""
Withdrawal service.

Handles withdrawal requests, balance validation, and admin processing.
"""

from decimal import Decimal
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TransactionStatus, TransactionType
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.transaction_repository import TransactionRepository


# Minimum withdrawal amount in USDT
MIN_WITHDRAWAL_AMOUNT = Decimal("5.0")


class WithdrawalService:
    """Withdrawal service for managing withdrawal requests."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize withdrawal service."""
        self.session = session
        self.transaction_repo = TransactionRepository(session)

    async def request_withdrawal(
        self,
        user_id: int,
        amount: Decimal,
        available_balance: Decimal,
    ) -> tuple[Optional[Transaction], Optional[str]]:
        """
        Request withdrawal.

        Args:
            user_id: User ID
            amount: Withdrawal amount
            available_balance: User's available balance (from UserService)

        Returns:
            Tuple of (transaction, error_message)
        """
        # Validate amount
        if amount < MIN_WITHDRAWAL_AMOUNT:
            return None, (
                f"Минимальная сумма вывода: "
                f"{MIN_WITHDRAWAL_AMOUNT} USDT"
            )

        # Get user with wallet address (with row lock)
        stmt = select(User).where(User.id == user_id).with_for_update()
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return None, "Пользователь не найден"

        # Check balance
        if available_balance < amount:
            return None, (
                f"Недостаточно средств. Доступно: "
                f"{available_balance:.2f} USDT"
            )

        # Create withdrawal transaction
        transaction = await self.transaction_repo.create(
            user_id=user_id,
            type=TransactionType.WITHDRAWAL.value,
            amount=amount,
            to_address=user.wallet_address,
            status=TransactionStatus.PENDING.value,
        )

        await self.session.commit()

        logger.info(
            "Withdrawal request created",
            extra={
                "transaction_id": transaction.id,
                "user_id": user_id,
                "amount": str(amount),
            },
        )

        return transaction, None

    async def get_pending_withdrawals(
        self,
    ) -> list[Transaction]:
        """
        Get pending withdrawals (for admin).

        Returns:
            List of pending withdrawal transactions
        """
        stmt = (
            select(Transaction)
            .where(
                Transaction.type == TransactionType.WITHDRAWAL.value,
                Transaction.status == TransactionStatus.PENDING.value,
            )
            .order_by(Transaction.created_at.asc())
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_withdrawals(
        self,
        user_id: int,
        page: int = 1,
        limit: int = 10,
    ) -> dict:
        """
        Get user withdrawal history.

        Args:
            user_id: User ID
            page: Page number (1-indexed)
            limit: Items per page

        Returns:
            Dict with withdrawals, total, page, pages
        """
        offset = (page - 1) * limit

        # Get total count
        count_stmt = select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.WITHDRAWAL.value,
        )
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))

        # Get paginated withdrawals
        stmt = (
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.WITHDRAWAL.value,
            )
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        withdrawals = list(result.scalars().all())

        pages = (total + limit - 1) // limit  # Ceiling division

        return {
            "withdrawals": withdrawals,
            "total": total,
            "page": page,
            "pages": pages,
        }

    async def cancel_withdrawal(
        self, transaction_id: int, user_id: int
    ) -> tuple[bool, Optional[str]]:
        """
        Cancel withdrawal (by user, only if pending).

        Args:
            transaction_id: Transaction ID
            user_id: User ID (for authorization)

        Returns:
            Tuple of (success, error_message)
        """
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.WITHDRAWAL.value,
            Transaction.status == TransactionStatus.PENDING.value,
        )

        result = await self.session.execute(stmt)
        transaction = result.scalar_one_or_none()

        if not transaction:
            return False, "Заявка не найдена или не может быть отменена"

        transaction.status = TransactionStatus.FAILED.value
        await self.session.commit()

        logger.info(
            "Withdrawal cancelled by user",
            extra={"transaction_id": transaction_id, "user_id": user_id},
        )

        return True, None

    async def approve_withdrawal(
        self, transaction_id: int, tx_hash: str
    ) -> tuple[bool, Optional[str]]:
        """
        Approve withdrawal (admin only).

        Args:
            transaction_id: Transaction ID
            tx_hash: Blockchain transaction hash

        Returns:
            Tuple of (success, error_message)
        """
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.type == TransactionType.WITHDRAWAL.value,
            Transaction.status == TransactionStatus.PENDING.value,
        )

        result = await self.session.execute(stmt)
        withdrawal = result.scalar_one_or_none()

        if not withdrawal:
            return (
                False,
                "Заявка на вывод не найдена или уже обработана",
            )

        # Update withdrawal status
        withdrawal.status = TransactionStatus.CONFIRMED.value
        withdrawal.tx_hash = tx_hash
        await self.session.commit()

        logger.info(
            "Withdrawal approved",
            extra={
                "transaction_id": transaction_id,
                "user_id": withdrawal.user_id,
                "amount": withdrawal.amount,
                "tx_hash": tx_hash,
            },
        )

        return True, None

    async def reject_withdrawal(
        self, transaction_id: int, reason: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Reject withdrawal (admin only).

        Args:
            transaction_id: Transaction ID
            reason: Rejection reason (for logging)

        Returns:
            Tuple of (success, error_message)
        """
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.type == TransactionType.WITHDRAWAL.value,
            Transaction.status == TransactionStatus.PENDING.value,
        )

        result = await self.session.execute(stmt)
        withdrawal = result.scalar_one_or_none()

        if not withdrawal:
            return (
                False,
                "Заявка на вывод не найдена или уже обработана",
            )

        # Update withdrawal status
        withdrawal.status = TransactionStatus.FAILED.value
        await self.session.commit()

        logger.info(
            "Withdrawal rejected",
            extra={
                "transaction_id": transaction_id,
                "user_id": withdrawal.user_id,
                "amount": withdrawal.amount,
                "reason": reason,
            },
        )

        return True, None

    async def get_withdrawal_by_id(
        self, transaction_id: int
    ) -> Optional[Transaction]:
        """
        Get withdrawal by ID (admin only).

        Args:
            transaction_id: Transaction ID

        Returns:
            Transaction or None
        """
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.type == TransactionType.WITHDRAWAL.value,
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def get_min_withdrawal_amount() -> Decimal:
        """
        Get minimum withdrawal amount.

        Returns:
            Minimum withdrawal amount in USDT
        """
        return MIN_WITHDRAWAL_AMOUNT
