"""
RewardSession repository.

Data access layer for RewardSession model.
"""

from typing import Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reward_session import RewardSession
from app.repositories.base import BaseRepository


class RewardSessionRepository(BaseRepository[RewardSession]):
    """RewardSession repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize reward session repository."""
        super().__init__(RewardSession, session)

    async def get_active_session(
        self,
    ) -> Optional[RewardSession]:
        """
        Get currently active reward session.

        Returns:
            Active session or None
        """
        now = datetime.now()

        stmt = (
            select(RewardSession)
            .where(RewardSession.is_active == True)
            .where(RewardSession.start_date <= now)
            .where(RewardSession.end_date >= now)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_session(
        self,
    ) -> Optional[RewardSession]:
        """
        Get latest reward session.

        Returns:
            Latest session or None
        """
        stmt = (
            select(RewardSession)
            .order_by(RewardSession.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
