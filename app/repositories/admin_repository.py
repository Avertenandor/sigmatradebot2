"""
Admin repository.

Data access layer for Admin model.
"""

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.repositories.base import BaseRepository


class AdminRepository(BaseRepository[Admin]):
    """Admin repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize admin repository."""
        super().__init__(Admin, session)

    async def get_by_telegram_id(
        self, telegram_id: int
    ) -> Optional[Admin]:
        """
        Get admin by Telegram ID.

        Args:
            telegram_id: Telegram admin ID

        Returns:
            Admin or None
        """
        return await self.get_by(telegram_id=telegram_id)

    async def get_by_role(self, role: str) -> List[Admin]:
        """
        Get admins by role.

        Args:
            role: Admin role (admin/extended_admin/super_admin)

        Returns:
            List of admins
        """
        return await self.find_by(role=role)

    async def get_super_admins(self) -> List[Admin]:
        """
        Get all super admins.

        Returns:
            List of super admins
        """
        return await self.get_by_role("super_admin")

    async def get_extended_admins(self) -> List[Admin]:
        """
        Get all extended admins.

        Returns:
            List of extended admins
        """
        return await self.get_by_role("extended_admin")
