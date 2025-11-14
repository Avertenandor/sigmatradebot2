"""
Transaction repository.

Data access layer for Transaction model.
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.enums import TransactionType, TransactionStatus
from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    """Transaction repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize transaction repository."""
        super().__init__(Transaction, session)

    async def get_by_user(
        self,
        user_id: int,
        type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Transaction]:
        """
        Get transactions by user.

        Args:
            user_id: User ID
            type: Optional transaction type filter
            status: Optional status filter

        Returns:
            List of transactions
        """
        filters = {"user_id": user_id}
        if type:
            filters["type"] = type
        if status:
            filters["status"] = status

        return await self.find_by(**filters)

    async def get_by_tx_hash(
        self, tx_hash: str
    ) -> Optional[Transaction]:
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
    ) -> List[Transaction]:
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
        self, type: Optional[str] = None
    ) -> List[Transaction]:
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
