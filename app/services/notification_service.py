"""
Notification service (+ PART5 multimedia support).

Sends notifications to users via Telegram.
"""

from typing import Any, Dict, List, Optional

from aiogram import Bot
from loguru import logger

from app.models.failed_notification import FailedNotification
from app.repositories.failed_notification_repository import (
    FailedNotificationRepository,
)


class NotificationService:
    """
    Notification service.

    Handles Telegram notifications with multimedia support (PART5).
    """

    def __init__(
        self,
        bot: Bot,
        failed_notification_repo: FailedNotificationRepository,
    ) -> None:
        """Initialize notification service."""
        self.bot = bot
        self.failed_repo = failed_notification_repo

    async def send_notification(
        self,
        user_telegram_id: int,
        message: str,
        critical: bool = False,
    ) -> bool:
        """
        Send text notification.

        Args:
            user_telegram_id: Telegram user ID
            message: Message text
            critical: Mark as critical

        Returns:
            True if sent successfully
        """
        try:
            await self.bot.send_message(
                chat_id=user_telegram_id, text=message
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to send notification: {e}",
                extra={"user_id": user_telegram_id},
            )

            # Save to failed notifications (PART5)
            await self._save_failed_notification(
                user_telegram_id,
                "text_message",
                message,
                str(e),
                critical,
            )
            return False

    async def send_photo(
        self,
        user_telegram_id: int,
        file_id: str,
        caption: Optional[str] = None,
    ) -> bool:
        """
        Send photo notification (PART5 multimedia).

        Args:
            user_telegram_id: Telegram user ID
            file_id: Telegram file ID
            caption: Photo caption

        Returns:
            True if sent successfully
        """
        try:
            await self.bot.send_photo(
                chat_id=user_telegram_id,
                photo=file_id,
                caption=caption,
            )
            return True
        except Exception as e:
            await self._save_failed_notification(
                user_telegram_id,
                "photo",
                caption or "",
                str(e),
                metadata={"file_id": file_id},
            )
            return False

    async def _save_failed_notification(
        self,
        user_telegram_id: int,
        notification_type: str,
        message: str,
        error: str,
        critical: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FailedNotification:
        """Save failed notification for retry (PART5)."""
        return await self.failed_repo.create(
            user_telegram_id=user_telegram_id,
            notification_type=notification_type,
            message=message,
            last_error=error,
            critical=critical,
            metadata=metadata,
        )
