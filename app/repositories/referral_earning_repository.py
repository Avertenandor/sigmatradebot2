"""
ReferralEarning repository.

Data access layer for ReferralEarning model.
"""

from typing import List, Optional
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral_earning import ReferralEarning
from app.repositories.base import BaseRepository


class ReferralEarningRepository(
    BaseRepository[ReferralEarning]
):
    """ReferralEarning repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize referral earning repository."""
        super().__init__(ReferralEarning, session)

    async def get_by_referral(
        self, referral_id: int, paid: Optional[bool] = None
    ) -> List[ReferralEarning]:
        """
        Get earnings by referral.

        Args:
            referral_id: Referral ID
            paid: Optional payment status filter

        Returns:
            List of earnings
        """
        filters = {"referral_id": referral_id}
        if paid is not None:
            filters["paid"] = paid

        return await self.find_by(**filters)

    async def get_unpaid_earnings(
        self, referral_id: Optional[int] = None
    ) -> List[ReferralEarning]:
        """
        Get unpaid earnings.

        Args:
            referral_id: Optional referral ID filter

        Returns:
            List of unpaid earnings
        """
        filters = {"paid": False}
        if referral_id:
            filters["referral_id"] = referral_id

        return await self.find_by(**filters)

    async def get_total_unpaid_amount(
        self, referral_id: int
    ) -> Decimal:
        """
        Get total unpaid earnings for referral.

        Args:
            referral_id: Referral ID

        Returns:
            Total unpaid amount
        """
        stmt = (
            select(func.sum(ReferralEarning.amount))
            .where(ReferralEarning.referral_id == referral_id)
            .where(ReferralEarning.paid == False)
        )
        result = await self.session.execute(stmt)
        total = result.scalar()
        return total or Decimal("0")
