"""
User repository.

Data access layer for User model.
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """User repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize user repository."""
        super().__init__(User, session)

    async def get_by_telegram_id(
        self, telegram_id: int
    ) -> Optional[User]:
        """
        Get user by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            User or None
        """
        return await self.get_by(telegram_id=telegram_id)

    async def get_by_wallet_address(
        self, wallet_address: str
    ) -> Optional[User]:
        """
        Get user by wallet address.

        Args:
            wallet_address: Wallet address

        Returns:
            User or None
        """
        return await self.get_by(wallet_address=wallet_address)

    async def get_with_referrals(
        self, user_id: int
    ) -> Optional[User]:
        """
        Get user with referrals loaded.

        Args:
            user_id: User ID

        Returns:
            User with referrals or None
        """
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.referrals_as_referrer),
                selectinload(User.referred_users),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_telegram_ids(self) -> List[int]:
        """
        Get all user Telegram IDs.

        Returns:
            List of Telegram IDs
        """
        stmt = select(User.telegram_id).where(User.is_banned == False)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_banned_users(self) -> List[User]:
        """
        Get all banned users.

        Returns:
            List of banned users
        """
        return await self.find_by(is_banned=True)

    async def get_verified_users(self) -> List[User]:
        """
        Get all verified users.

        Returns:
            List of verified users
        """
        return await self.find_by(is_verified=True)
