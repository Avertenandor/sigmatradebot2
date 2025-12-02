"""
Transaction repository.

Data access layer for Transaction model.
"""

from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TransactionStatus, TransactionType
from app.models.transaction import Transaction
from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    """Transaction repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize transaction repository."""
        super().__init__(Transaction, session)

    async def get_by_user(
        self,
        user_id: int,
        type: str | None = None,
        status: str | None = None,
    ) -> list[Transaction]:
        """
        Get transactions by user.

        Args:
            user_id: User ID
            type: Optional transaction type filter
            status: Optional status filter

        Returns:
            List of transactions
        """
        filters: dict[str, int | str] = {"user_id": user_id}
        if type:
            filters["type"] = type
        if status:
            filters["status"] = status

        return await self.find_by(**filters)

    async def get_by_tx_hash(
        self, tx_hash: str
    ) -> Transaction | None:
        """
        Get transaction by hash.

        Args:
            tx_hash: Transaction hash

        Returns:
            Transaction or None
        """
        return await self.get_by(tx_hash=tx_hash)

    async def get_withdrawals(
        self, user_id: int
    ) -> list[Transaction]:
        """
        Get user withdrawals.

        Args:
            user_id: User ID

        Returns:
            List of withdrawal transactions
        """
        return await self.get_by_user(
            user_id=user_id,
            type=TransactionType.WITHDRAWAL.value,
        )

    async def get_pending_transactions(
        self, type: str | None = None
    ) -> list[Transaction]:
        """
        Get pending transactions.

        Args:
            type: Optional transaction type filter

        Returns:
            List of pending transactions
        """
        filters = {"status": TransactionStatus.PENDING.value}
        if type:
            filters["type"] = type

        return await self.find_by(**filters)

    async def get_total_withdrawn(self, user_id: int) -> Decimal:
        """
        Get total withdrawn amount (completed + pending + processing).
        Excludes FAILED and REJECTED.

        Args:
            user_id: User ID

        Returns:
            Total amount
        """
        stmt = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .where(Transaction.type == TransactionType.WITHDRAWAL.value)
            .where(
                or_(
                    Transaction.status == TransactionStatus.CONFIRMED.value,
                    Transaction.status == TransactionStatus.PENDING.value,
                    Transaction.status == TransactionStatus.PROCESSING.value,
                )
            )
        )
        result = await self.session.execute(stmt)
        transactions = result.scalars().all()
        
        if not transactions:
            return Decimal("0")
            
        return sum((t.amount for t in transactions), Decimal("0"))

    async def get_total_withdrawn_today(self) -> Decimal:
        """
        Get total withdrawn amount for today (all users).
        Used for global daily limit check.

        Returns:
            Total amount
        """
        from datetime import datetime, UTC
        
        today_start = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # Convert to naive datetime to match Transaction model's naive DateTime column
        # This avoids "can't subtract offset-naive and offset-aware datetimes" error
        today_start_naive = today_start.replace(tzinfo=None)
        
        stmt = (
            select(Transaction)
            .where(Transaction.type == TransactionType.WITHDRAWAL.value)
            .where(Transaction.created_at >= today_start_naive)
            .where(
                or_(
                    Transaction.status == TransactionStatus.CONFIRMED.value,
                    Transaction.status == TransactionStatus.PENDING.value,
                    Transaction.status == TransactionStatus.PROCESSING.value,
                )
            )
        )
        result = await self.session.execute(stmt)
        transactions = result.scalars().all()
        
        if not transactions:
            return Decimal("0")
            
        return sum((t.amount for t in transactions), Decimal("0"))
