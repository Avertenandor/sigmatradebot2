"""
Appeal repository.

Data access layer for Appeal model.
"""


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appeal import Appeal, AppealStatus
from app.repositories.base import BaseRepository


class AppealRepository(BaseRepository[Appeal]):
    """Appeal repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize appeal repository."""
        super().__init__(Appeal, session)

    async def get_by_user(
        self, user_id: int, status: str | None = None
    ) -> list[Appeal]:
        """
        Get appeals by user.

        Args:
            user_id: User ID
            status: Optional status filter

        Returns:
            List of appeals
        """
        filters: dict[str, int | str] = {"user_id": user_id}
        if status:
            filters["status"] = status

        return await self.find_by(**filters)

    async def get_by_blacklist(
        self, blacklist_id: int
    ) -> list[Appeal]:
        """
        Get appeals by blacklist entry.

        Args:
            blacklist_id: Blacklist entry ID

        Returns:
            List of appeals
        """
        return await self.find_by(blacklist_id=blacklist_id)

    async def get_pending_appeals(
        self
    ) -> list[Appeal]:
        """
        Get all pending appeals.

        Returns:
            List of pending appeals
        """
        return await self.find_by(status=AppealStatus.PENDING)

    async def get_active_appeal_for_user(
        self, user_id: int, blacklist_id: int
    ) -> Appeal | None:
        """
        Get active (pending or under_review) appeal for user and
        blacklist entry.

        Args:
            user_id: User ID
            blacklist_id: Blacklist entry ID

        Returns:
            Appeal or None
        """
        stmt = (
            select(Appeal)
            .where(
                Appeal.user_id == user_id,
                Appeal.blacklist_id == blacklist_id,
                Appeal.status.in_([
                    AppealStatus.PENDING,
                    AppealStatus.UNDER_REVIEW
                ])
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_status(
        self, status: str
    ) -> list[Appeal]:
        """
        Get appeals by status.

        Args:
            status: Appeal status

        Returns:
            List of appeals
        """
        return await self.find_by(status=status)

    async def get_active_appeals_for_user(
        self, user_id: int
    ) -> list[Appeal]:
        """
        Get all active (pending or under_review) appeals for user.

        Args:
            user_id: User ID

        Returns:
            List of active appeals
        """
        stmt = (
            select(Appeal)
            .where(
                Appeal.user_id == user_id,
                Appeal.status.in_([
                    AppealStatus.PENDING,
                    AppealStatus.UNDER_REVIEW
                ])
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())