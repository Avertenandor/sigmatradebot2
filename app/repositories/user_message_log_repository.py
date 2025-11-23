"""
UserMessageLog repository.

Handles database operations for user message logs.
"""

from datetime import UTC, datetime

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_message_log import UserMessageLog


class UserMessageLogRepository:
    """Repository for UserMessageLog operations."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository.

        Args:
            session: Database session
        """
        self.session = session

    async def create(
        self,
        telegram_id: int,
        message_text: str,
        user_id: int | None = None,
    ) -> UserMessageLog:
        """
        Create new message log entry.

        Args:
            telegram_id: Telegram user ID
            message_text: Message content
            user_id: Optional DB user ID

        Returns:
            Created UserMessageLog
        """
        log = UserMessageLog(
            telegram_id=telegram_id,
            message_text=message_text,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def get_user_messages(
        self,
        telegram_id: int,
        limit: int = 500,
        offset: int = 0,
    ) -> list[UserMessageLog]:
        """
        Get user messages ordered by timestamp (newest first).

        Args:
            telegram_id: Telegram user ID
            limit: Maximum number of messages
            offset: Offset for pagination

        Returns:
            List of UserMessageLog
        """
        stmt = (
            select(UserMessageLog)
            .where(UserMessageLog.telegram_id == telegram_id)
            .order_by(desc(UserMessageLog.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_user_messages(self, telegram_id: int) -> int:
        """
        Count total messages for user.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Message count
        """
        from sqlalchemy import func

        stmt = select(func.count(UserMessageLog.id)).where(
            UserMessageLog.telegram_id == telegram_id
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def cleanup_old_messages(
        self, telegram_id: int, keep_last: int = 500
    ) -> int:
        """
        Delete old messages, keeping only last N.

        Args:
            telegram_id: Telegram user ID
            keep_last: Number of messages to keep

        Returns:
            Number of deleted messages
        """
        # Get ID of the Nth newest message
        subquery = (
            select(UserMessageLog.id)
            .where(UserMessageLog.telegram_id == telegram_id)
            .order_by(desc(UserMessageLog.created_at))
            .limit(1)
            .offset(keep_last - 1)
        )
        result = await self.session.execute(subquery)
        cutoff_id = result.scalar()

        if cutoff_id is None:
            # Less than keep_last messages, nothing to delete
            return 0

        # Delete messages older than cutoff
        stmt = delete(UserMessageLog).where(
            UserMessageLog.telegram_id == telegram_id,
            UserMessageLog.id < cutoff_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0

    async def search_messages(
        self,
        telegram_id: int,
        search_text: str,
        limit: int = 100,
    ) -> list[UserMessageLog]:
        """
        Search messages by text content.

        Args:
            telegram_id: Telegram user ID
            search_text: Text to search for
            limit: Maximum results

        Returns:
            List of matching UserMessageLog
        """
        stmt = (
            select(UserMessageLog)
            .where(
                UserMessageLog.telegram_id == telegram_id,
                UserMessageLog.message_text.ilike(f"%{search_text}%"),
            )
            .order_by(desc(UserMessageLog.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_all_user_messages(self, telegram_id: int) -> int:
        """
        Delete all messages for user.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Number of deleted messages
        """
        stmt = delete(UserMessageLog).where(
            UserMessageLog.telegram_id == telegram_id
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0

