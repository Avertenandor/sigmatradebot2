"""
FailedNotification repository (КРИТИЧНО - PART5).

Data access layer for FailedNotification model.
"""

from typing import List

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
    ) -> List[FailedNotification]:
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
    ) -> List[FailedNotification]:
        """
        Get critical unresolved notifications.

        Returns:
            List of critical unresolved notifications
        """
        return await self.get_unresolved(critical_only=True)

    async def get_by_user(
        self, user_telegram_id: int
    ) -> List[FailedNotification]:
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
    ) -> List[FailedNotification]:
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
