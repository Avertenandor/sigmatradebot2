"""
Message Log Middleware.

Logs all text messages from users to database for admin monitoring.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_message_log_service import UserMessageLogService


class MessageLogMiddleware(BaseMiddleware):
    """
    Message log middleware.

    Logs all text messages (not buttons/callbacks) to database.
    Keeps last 500 messages per user.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Log message and continue processing."""
        # Only log text messages
        if isinstance(event, Message) and event.text:
            # Skip button clicks (they have reply_markup)
            # Log only typed messages
            if not event.reply_markup:
                telegram_id = (
                    event.from_user.id if event.from_user else None
                )
                if telegram_id:
                    session: AsyncSession | None = data.get("session")
                    if session:
                        try:
                            # Get user_id from data if available
                            user = data.get("user")
                            user_id = user.id if user else None

                            # Log message
                            service = UserMessageLogService(session)
                            await service.log_message(
                                telegram_id=telegram_id,
                                message_text=event.text,
                                user_id=user_id,
                            )
                            logger.debug(
                                f"Logged message from user {telegram_id}: "
                                f"'{event.text[:50]}...'"
                            )
                        except Exception as e:
                            # Don't fail if logging fails
                            logger.warning(
                                f"Failed to log message from user "
                                f"{telegram_id}: {e}"
                            )

        # Continue processing
        return await handler(event, data)

