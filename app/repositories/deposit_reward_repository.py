"""
DepositReward repository.

Data access layer for DepositReward model.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deposit_reward import DepositReward
from app.repositories.base import BaseRepository


class DepositRewardRepository(BaseRepository[DepositReward]):
    """DepositReward repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize deposit reward repository."""
        super().__init__(DepositReward, session)

    async def get_by_user(
        self, user_id: int, paid: bool | None = None
    ) -> list[DepositReward]:
        """
        Get rewards by user.

        Args:
            user_id: User ID
            paid: Optional payment status filter

        Returns:
            List of rewards
        """
        filters = {"user_id": user_id}
        if paid is not None:
            filters["paid"] = paid

        return await self.find_by(**filters)

    async def get_unpaid_rewards(
        self, user_id: int | None = None
    ) -> list[DepositReward]:
        """
        Get unpaid rewards.

        Args:
            user_id: Optional user ID filter

        Returns:
            List of unpaid rewards
        """
        filters = {"paid": False}
        if user_id:
            filters["user_id"] = user_id

        return await self.find_by(**filters)

    async def get_by_session(
        self, reward_session_id: int
    ) -> list[DepositReward]:
        """
        Get rewards by session.

        Args:
            reward_session_id: Reward session ID

        Returns:
            List of rewards
        """
        return await self.find_by(
            reward_session_id=reward_session_id
        )

    async def get_total_unpaid_amount(
        self, user_id: int
    ) -> Decimal:
        """
        Get total unpaid reward amount for user.

        Args:
            user_id: User ID

        Returns:
            Total unpaid amount
        """
        stmt = (
            select(func.sum(DepositReward.reward_amount))
            .where(DepositReward.user_id == user_id)
            .where(not DepositReward.paid)
        )
        result = await self.session.execute(stmt)
        total = result.scalar()
        return total or Decimal("0")
