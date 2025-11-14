"""
Referral repository.

Data access layer for Referral model.
"""

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import Referral
from app.repositories.base import BaseRepository


class ReferralRepository(BaseRepository[Referral]):
    """Referral repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize referral repository."""
        super().__init__(Referral, session)

    async def get_by_referrer(
        self, referrer_id: int, level: int = None
    ) -> List[Referral]:
        """
        Get referrals by referrer.

        Args:
            referrer_id: Referrer user ID
            level: Optional level filter (1-3)

        Returns:
            List of referrals
        """
        filters = {"referrer_id": referrer_id}
        if level:
            filters["level"] = level

        return await self.find_by(**filters)

    async def get_by_referral_user(
        self, referral_user_id: int
    ) -> List[Referral]:
        """
        Get referrals where user is the referral.

        Args:
            referral_user_id: Referral user ID

        Returns:
            List of referrals
        """
        return await self.find_by(
            referral_user_id=referral_user_id
        )

    async def get_level_1_referrals(
        self, referrer_id: int
    ) -> List[Referral]:
        """
        Get level 1 (direct) referrals.

        Args:
            referrer_id: Referrer user ID

        Returns:
            List of level 1 referrals
        """
        return await self.get_by_referrer(
            referrer_id=referrer_id, level=1
        )

    async def count_by_level(
        self, referrer_id: int, level: int
    ) -> int:
        """
        Count referrals by level.

        Args:
            referrer_id: Referrer user ID
            level: Referral level (1-3)

        Returns:
            Count of referrals
        """
        return await self.count(
            referrer_id=referrer_id, level=level
        )
