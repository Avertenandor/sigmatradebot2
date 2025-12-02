"""
ReferralEarning repository.

Data access layer for ReferralEarning model.
"""

from decimal import Decimal

from sqlalchemy import func, select
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
        self, referral_id: int, paid: bool | None = None
    ) -> list[ReferralEarning]:
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
        self, referral_id: int | None = None
    ) -> list[ReferralEarning]:
        """
        Get unpaid earnings.

        Args:
            referral_id: Optional referral ID filter

        Returns:
            List of unpaid earnings
        """
        filters: dict[str, bool | int] = {"paid": False}
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
            .where(ReferralEarning.paid == False)  # noqa: E712
        )
        result = await self.session.execute(stmt)
        total = result.scalar()
        return total or Decimal("0")

    async def find_by_referral_ids(
        self, referral_ids: list[int]
    ) -> list[ReferralEarning]:
        """
        Get all earnings for multiple referral IDs.

        Args:
            referral_ids: List of referral IDs

        Returns:
            List of earnings
        """
        if not referral_ids:
            return []

        stmt = select(ReferralEarning).where(
            ReferralEarning.referral_id.in_(referral_ids)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_unpaid_by_referral_ids(
        self,
        referral_ids: list[int],
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ReferralEarning]:
        """
        Get unpaid earnings for multiple referral IDs.

        Args:
            referral_ids: List of referral IDs
            limit: Optional limit
            offset: Optional offset

        Returns:
            List of unpaid earnings
        """
        if not referral_ids:
            return []

        stmt = (
            select(ReferralEarning)
            .where(ReferralEarning.referral_id.in_(referral_ids))
            .where(ReferralEarning.paid == False)  # noqa: E712
            .order_by(ReferralEarning.created_at.desc())
        )

        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_for_referrer(
        self, referrer_id: int
    ) -> list[ReferralEarning]:
        """
        Get all earnings for a referrer through their referrals.

        Args:
            referrer_id: Referrer user ID

        Returns:
            List of all earnings
        """
        from app.models.referral import Referral

        # Join with Referral to get earnings where the referrer matches
        stmt = (
            select(ReferralEarning)
            .join(Referral, ReferralEarning.referral_id == Referral.id)
            .where(Referral.referrer_id == referrer_id)
            .order_by(ReferralEarning.created_at.desc())
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
