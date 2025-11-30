"""
User notification service.

Business logic for managing user notification preferences.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_notification_settings import UserNotificationSettings
from app.repositories.user_notification_settings_repository import (
    UserNotificationSettingsRepository,
)


class UserNotificationService:
    """Service for managing user notification settings."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize notification service.

        Args:
            session: Database session
        """
        self.session = session
        self.repo = UserNotificationSettingsRepository(session)

    async def get_settings(
        self, user_id: int
    ) -> UserNotificationSettings:
        """
        Get notification settings for user, creating defaults if not exists.

        Args:
            user_id: User ID

        Returns:
            UserNotificationSettings instance
        """
        settings = await self.repo.get_by_user_id(user_id)
        
        if not settings:
            # Create default settings
            settings = await self.repo.create_or_update(
                user_id,
                deposit_notifications=True,
                withdrawal_notifications=True,
                roi_notifications=True,
                marketing_notifications=False,
            )
            await self.session.flush()
        
        return settings

    async def update_settings(
        self, user_id: int, **kwargs
    ) -> UserNotificationSettings:
        """
        Update notification settings for user.

        Args:
            user_id: User ID
            **kwargs: Settings to update:
                - deposit_notifications: bool
                - withdrawal_notifications: bool
                - roi_notifications: bool
                - marketing_notifications: bool

        Returns:
            Updated UserNotificationSettings instance
        """
        return await self.repo.create_or_update(user_id, **kwargs)

