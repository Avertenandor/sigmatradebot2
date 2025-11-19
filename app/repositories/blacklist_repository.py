"""
Blacklist repository.

Data access layer for Blacklist model.
"""


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
    ) -> Blacklist | None:
        """
        Get blacklist entry by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Blacklist entry or None
        """
        return await self.get_by(telegram_id=telegram_id)

    async def find_by_telegram_id(
        self, telegram_id: int
    ) -> Blacklist | None:
        """
        Find blacklist entry by Telegram ID (alias for get_by_telegram_id).

        Args:
            telegram_id: Telegram user ID

        Returns:
            Blacklist entry or None
        """
        return await self.get_by_telegram_id(telegram_id)

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
        entry = await self.get_by_telegram_id(telegram_id)
        return entry is not None and entry.is_active

    async def find_by_wallet(
        self, wallet_address: str
    ) -> Blacklist | None:
        """
        Find blacklist entry by wallet address.

        Args:
            wallet_address: Wallet address

        Returns:
            Blacklist entry or None
        """
        from sqlalchemy import select
        normalized = wallet_address.lower()
        stmt = (
            select(Blacklist)
            .where(
                Blacklist.wallet_address == normalized,
                Blacklist.is_active.is_(True)
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_blacklist(
        self, limit: int = 100, offset: int = 0
    ) -> list[Blacklist]:
        """
        Get active blacklist entries.

        Args:
            limit: Maximum entries to return
            offset: Offset for pagination

        Returns:
            List of active Blacklist entries
        """
        from sqlalchemy import select
        # Note: is_active is stored as Boolean in DB after migration
        stmt = (
            select(Blacklist)
            .where(Blacklist.is_active.is_(True))
            .limit(limit)
            .offset(offset)
            .order_by(Blacklist.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_active(self) -> int:
        """
        Count active blacklist entries.

        Returns:
            Number of active entries
        """
        from sqlalchemy import func, select
        # Note: is_active is stored as Boolean in DB after migration
        stmt = (
            select(func.count())
            .select_from(Blacklist)
            .where(Blacklist.is_active.is_(True))
        )
        result = await self.session.execute(stmt)
        count = result.scalar()
        return int(count) if count is not None else 0
