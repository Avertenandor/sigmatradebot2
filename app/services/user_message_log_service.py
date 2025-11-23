"""
UserMessageLog service.

Business logic for user message logging.
"""

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_message_log import UserMessageLog
from app.repositories.user_message_log_repository import (
    UserMessageLogRepository,
)


class UserMessageLogService:
    """Service for user message logging."""

    MAX_MESSAGES_PER_USER = 500

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize service.

        Args:
            session: Database session
        """
        self.session = session
        self.repo = UserMessageLogRepository(session)

    async def log_message(
        self,
        telegram_id: int,
        message_text: str,
        user_id: int | None = None,
    ) -> UserMessageLog:
        """
        Log user message and cleanup old messages.

        Args:
            telegram_id: Telegram user ID
            message_text: Message content
            user_id: Optional DB user ID

        Returns:
            Created UserMessageLog
        """
        # Create log entry
        log = await self.repo.create(
            telegram_id=telegram_id,
            message_text=message_text,
            user_id=user_id,
        )

        # Cleanup old messages (keep last 500)
        try:
            deleted_count = await self.repo.cleanup_old_messages(
                telegram_id=telegram_id,
                keep_last=self.MAX_MESSAGES_PER_USER,
            )
            if deleted_count > 0:
                logger.debug(
                    f"Cleaned up {deleted_count} old messages "
                    f"for user {telegram_id}"
                )
        except Exception as e:
            logger.warning(
                f"Failed to cleanup old messages for user {telegram_id}: {e}"
            )
            # Don't fail if cleanup fails

        return log

    async def get_user_messages(
        self,
        telegram_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[UserMessageLog], int]:
        """
        Get user messages with pagination.

        Args:
            telegram_id: Telegram user ID
            limit: Messages per page
            offset: Offset for pagination

        Returns:
            Tuple of (messages, total_count)
        """
        messages = await self.repo.get_user_messages(
            telegram_id=telegram_id,
            limit=limit,
            offset=offset,
        )
        total = await self.repo.count_user_messages(telegram_id=telegram_id)
        return messages, total

    async def search_messages(
        self,
        telegram_id: int,
        search_text: str,
        limit: int = 100,
    ) -> list[UserMessageLog]:
        """
        Search user messages.

        Args:
            telegram_id: Telegram user ID
            search_text: Text to search
            limit: Maximum results

        Returns:
            List of matching messages
        """
        return await self.repo.search_messages(
            telegram_id=telegram_id,
            search_text=search_text,
            limit=limit,
        )

    async def delete_all_messages(self, telegram_id: int) -> int:
        """
        Delete all messages for user.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Number of deleted messages
        """
        count = await self.repo.delete_all_user_messages(telegram_id)
        logger.info(f"Deleted {count} messages for user {telegram_id}")
        return count

