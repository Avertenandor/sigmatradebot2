"""
Blacklist repository.

Data access layer for Blacklist model.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blacklist import Blacklist
from app.repositories.base import BaseRepository


class BlacklistRepository(BaseRepository[Blacklist]):
    """Blacklist repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize blacklist repository."""
        super().__init__(Blacklist, session)

    async def get_by_telegram_id(
        self, telegram_id: int
    ) -> Optional[Blacklist]:
        """
        Get blacklist entry by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Blacklist entry or None
        """
        return await self.get_by(telegram_id=telegram_id)

    async def is_blacklisted(
        self, telegram_id: int
    ) -> bool:
        """
        Check if user is blacklisted.

        Args:
            telegram_id: Telegram user ID

        Returns:
            True if blacklisted, False otherwise
        """
        return await self.exists(telegram_id=telegram_id)
