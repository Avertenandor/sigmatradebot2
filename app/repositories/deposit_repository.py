"""
Deposit repository.

Data access layer for Deposit model.
"""

from typing import List, Optional
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deposit import Deposit
from app.models.enums import TransactionStatus
from app.repositories.base import BaseRepository


class DepositRepository(BaseRepository[Deposit]):
    """Deposit repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize deposit repository."""
        super().__init__(Deposit, session)

    async def get_by_user(
        self, user_id: int, status: Optional[str] = None
    ) -> List[Deposit]:
        """
        Get deposits by user.

        Args:
            user_id: User ID
            status: Optional status filter

        Returns:
            List of deposits
        """
        filters = {"user_id": user_id}
        if status:
            filters["status"] = status

        return await self.find_by(**filters)

    async def get_by_tx_hash(
        self, tx_hash: str
    ) -> Optional[Deposit]:
        """
        Get deposit by transaction hash.

        Args:
            tx_hash: Transaction hash

        Returns:
            Deposit or None
        """
        return await self.get_by(tx_hash=tx_hash)

    async def get_active_deposits(
        self, user_id: int
    ) -> List[Deposit]:
        """
        Get active deposits (ROI not completed).

        Args:
            user_id: User ID

        Returns:
            List of active deposits
        """
        stmt = (
            select(Deposit)
            .where(Deposit.user_id == user_id)
            .where(Deposit.is_roi_completed == False)
            .where(
                Deposit.status == TransactionStatus.CONFIRMED.value
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_level(
        self, user_id: int, level: int
    ) -> List[Deposit]:
        """
        Get deposits by user and level.

        Args:
            user_id: User ID
            level: Deposit level (1-5)

        Returns:
            List of deposits
        """
        return await self.find_by(user_id=user_id, level=level)

    async def get_pending_deposits(self) -> List[Deposit]:
        """
        Get all pending deposits.

        Returns:
            List of pending deposits
        """
        return await self.find_by(
            status=TransactionStatus.PENDING.value
        )

    async def get_total_deposited(
        self, user_id: int
    ) -> Decimal:
        """
        Get total deposited amount by user.

        Args:
            user_id: User ID

        Returns:
            Total deposited amount
        """
        deposits = await self.get_by(
            user_id=user_id,
            status=TransactionStatus.CONFIRMED.value,
        )
        if not deposits:
            return Decimal("0")

        return sum(d.amount for d in deposits)
