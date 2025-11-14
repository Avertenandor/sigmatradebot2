"""
User service.

Business logic for user management.
"""

from typing import Optional
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.blacklist_repository import (
    BlacklistRepository,
)


class UserService:
    """
    User service.

    Handles user registration, profile management, and referrals.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize user service.

        Args:
            session: Database session
        """
        self.session = session
        self.user_repo = UserRepository(session)
        self.blacklist_repo = BlacklistRepository(session)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User or None
        """
        return await self.user_repo.get_by_id(user_id)

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
        return await self.user_repo.get_by_telegram_id(
            telegram_id
        )

    async def register_user(
        self,
        telegram_id: int,
        wallet_address: str,
        financial_password: str,
        username: Optional[str] = None,
        referrer_telegram_id: Optional[int] = None,
    ) -> User:
        """
        Register new user with referral support.

        Args:
            telegram_id: Telegram user ID
            wallet_address: User's wallet address
            financial_password: Bcrypt-hashed password
            username: Telegram username (optional)
            referrer_telegram_id: Referrer's Telegram ID

        Returns:
            Created user

        Raises:
            ValueError: If user already exists or blacklisted
        """
        # Check if blacklisted
        is_blacklisted = await self.blacklist_repo.is_blacklisted(
            telegram_id
        )
        if is_blacklisted:
            raise ValueError("User is blacklisted")

        # Check if already exists
        existing = await self.user_repo.get_by_telegram_id(
            telegram_id
        )
        if existing:
            raise ValueError("User already registered")

        # Find referrer if provided
        referrer_id = None
        if referrer_telegram_id:
            referrer = await self.user_repo.get_by_telegram_id(
                referrer_telegram_id
            )
            if referrer:
                referrer_id = referrer.id

        # Create user
        user = await self.user_repo.create(
            telegram_id=telegram_id,
            username=username,
            wallet_address=wallet_address,
            financial_password=financial_password,
            referrer_id=referrer_id,
        )

        await self.session.commit()

        logger.info(
            "User registered",
            extra={
                "user_id": user.id,
                "telegram_id": telegram_id,
                "has_referrer": referrer_id is not None,
            },
        )

        return user

    async def update_profile(
        self, user_id: int, **data
    ) -> Optional[User]:
        """
        Update user profile.

        Args:
            user_id: User ID
            **data: Fields to update

        Returns:
            Updated user or None
        """
        user = await self.user_repo.update(user_id, **data)

        if user:
            await self.session.commit()
            logger.info(
                "User profile updated",
                extra={"user_id": user_id},
            )

        return user

    async def block_earnings(
        self, user_id: int, block: bool = True
    ) -> Optional[User]:
        """
        Block/unblock user earnings.

        Used during financial password recovery.

        Args:
            user_id: User ID
            block: True to block, False to unblock

        Returns:
            Updated user or None
        """
        return await self.update_profile(
            user_id, earnings_blocked=block
        )

    async def ban_user(
        self, user_id: int, ban: bool = True
    ) -> Optional[User]:
        """
        Ban/unban user.

        Args:
            user_id: User ID
            ban: True to ban, False to unban

        Returns:
            Updated user or None
        """
        return await self.update_profile(user_id, is_banned=ban)

    async def get_all_telegram_ids(self) -> list[int]:
        """
        Get all user Telegram IDs.

        Returns:
            List of Telegram IDs
        """
        return await self.user_repo.get_all_telegram_ids()

    async def verify_financial_password(
        self, user_id: int, password: str
    ) -> bool:
        """
        Verify financial password.

        Args:
            user_id: User ID
            password: Plain password to verify

        Returns:
            True if password matches
        """
        import bcrypt

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return False

        return bcrypt.checkpw(
            password.encode(),
            user.financial_password.encode(),
        )
