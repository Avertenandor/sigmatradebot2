"""
SystemSetting repository.

Data access layer for SystemSetting model.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting
from app.repositories.base import BaseRepository


class SystemSettingRepository(BaseRepository[SystemSetting]):
    """SystemSetting repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize system setting repository."""
        super().__init__(SystemSetting, session)

    async def get_value(
        self, key: str, default: Optional[str] = None
    ) -> Optional[str]:
        """
        Get setting value by key.

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value or default
        """
        setting = await self.get_by(key=key)
        return setting.value if setting else default

    async def set_value(
        self, key: str, value: str
    ) -> SystemSetting:
        """
        Set setting value.

        Creates new setting or updates existing.

        Args:
            key: Setting key
            value: Setting value

        Returns:
            Updated/created setting
        """
        setting = await self.get_by(key=key)

        if setting:
            setting.value = value
            await self.session.flush()
            await self.session.refresh(setting)
            return setting
        else:
            return await self.create(key=key, value=value)

    async def delete_by_key(self, key: str) -> bool:
        """
        Delete setting by key.

        Args:
            key: Setting key

        Returns:
            True if deleted, False if not found
        """
        setting = await self.get_by(key=key)
        if not setting:
            return False

        await self.session.delete(setting)
        await self.session.flush()
        return True
