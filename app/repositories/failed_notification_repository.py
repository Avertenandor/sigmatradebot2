"""
FailedNotification repository (КРИТИЧНО - PART5).

Data access layer for FailedNotification model.
"""


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.failed_notification import FailedNotification
from app.repositories.base import BaseRepository


class FailedNotificationRepository(
    BaseRepository[FailedNotification]
):
    """
    FailedNotification repository (КРИТИЧНО из PART5).

    Tracks failed notification attempts for retry.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize failed notification repository."""
        super().__init__(FailedNotification, session)

    async def get_unresolved(
        self, critical_only: bool = False
    ) -> list[FailedNotification]:
        """
        Get unresolved failed notifications.

        Args:
            critical_only: Only return critical notifications

        Returns:
            List of unresolved notifications
        """
        filters = {"resolved": False}
        if critical_only:
            filters["critical"] = True

        return await self.find_by(**filters)

    async def get_critical_unresolved(
        self,
    ) -> list[FailedNotification]:
        """
        Get critical unresolved notifications.

        Returns:
            List of critical unresolved notifications
        """
        return await self.get_unresolved(critical_only=True)

    async def get_by_user(
        self, user_telegram_id: int
    ) -> list[FailedNotification]:
        """
        Get failed notifications by user.

        Args:
            user_telegram_id: Telegram user ID

        Returns:
            List of failed notifications
        """
        return await self.find_by(
            user_telegram_id=user_telegram_id
        )

    async def get_by_type(
        self, notification_type: str
    ) -> list[FailedNotification]:
        """
        Get failed notifications by type.

        Args:
            notification_type: Notification type

        Returns:
            List of failed notifications
        """
        return await self.find_by(
            notification_type=notification_type
        )

    async def get_pending_for_retry(
        self, max_attempts: int = 5, limit: int = 100
    ) -> list[FailedNotification]:
        """
        Get failed notifications ready for retry.

        R8-3: Sorted by priority (critical first, then by creation time).

        Args:
            max_attempts: Maximum retry attempts
            limit: Maximum number of results

        Returns:
            List of pending notifications (sorted by priority)
        """
        from sqlalchemy import desc

        stmt = (
            select(FailedNotification)
            .where(FailedNotification.resolved == False)  # noqa: E712
            .where(FailedNotification.attempt_count < max_attempts)
            # R8-3: Sort by priority (critical first), then by creation time
            .order_by(
                desc(FailedNotification.critical),  # Critical first (True before False)
                FailedNotification.created_at.asc()  # Then by age (oldest first)
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
