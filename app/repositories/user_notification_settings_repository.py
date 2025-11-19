"""
User notification settings repository.

Data access layer for UserNotificationSettings model.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_notification_settings import UserNotificationSettings
from app.repositories.base import BaseRepository


class UserNotificationSettingsRepository(
    BaseRepository[UserNotificationSettings]
):
    """User notification settings repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize notification settings repository."""
        super().__init__(UserNotificationSettings, session)

    async def get_by_user_id(
        self, user_id: int
    ) -> UserNotificationSettings | None:
        """
        Get notification settings by user ID.

        Args:
            user_id: User ID

        Returns:
            UserNotificationSettings or None
        """
        stmt = select(UserNotificationSettings).where(
            UserNotificationSettings.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_or_update(
        self, user_id: int, **kwargs
    ) -> UserNotificationSettings:
        """
        Create or update notification settings for user.

        Args:
            user_id: User ID
            **kwargs: Settings to update (deposit_notifications, etc.)

        Returns:
            UserNotificationSettings instance
        """
        existing = await self.get_by_user_id(user_id)
        
        if existing:
            # Update existing
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await self.session.flush()
            return existing
        else:
            # Create new
            settings = UserNotificationSettings(
                user_id=user_id,
                **kwargs
            )
            self.session.add(settings)
            await self.session.flush()
            return settings

