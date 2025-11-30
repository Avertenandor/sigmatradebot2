"""Logger Middleware - Log all incoming updates."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, User
from loguru import logger


class LoggerMiddleware(BaseMiddleware):
    """
    Logger middleware.

    Logs all incoming updates with request ID tracking.
    Includes language_code as proxy for user location/region.
    """

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]], Awaitable[Any]
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Log update and process."""
        # Get request ID (set by RequestIDMiddleware)
        request_id = data.get("request_id", "unknown")

        # Get user info (Telegram User, not DB User model)
        user: User | None = data.get("event_from_user")
        user_id = user.id if user else None
        username = user.username if user else None
        
        # Log language_code as a proxy for region (Telegram doesn't provide IP)
        language_code = user.language_code if user else None

        # Get update type - try from data first, then from event
        update: Update | None = data.get("event_update")
        update_type = "unknown"

        if update:
            if update.message:
                update_type = "message"
            elif update.callback_query:
                update_type = "callback_query"
            elif update.inline_query:
                update_type = "inline_query"
        elif isinstance(event, Message):
            update_type = "message"
        elif hasattr(event, "data"):  # CallbackQuery
            update_type = "callback_query"

        logger.info(
            f"[{request_id}] {update_type} from user {user_id} (@{username}) "
            f"[lang={language_code}]"
        )
        
        # Log message text for debugging
        if isinstance(event, Message) and event.text:
            logger.info(f"[{request_id}] Text: '{event.text}'")

        # Process
        try:
            result = await handler(event, data)
            logger.debug(f"[{request_id}] Handler completed successfully")
            return result

        except Exception as e:
            logger.error(f"[{request_id}] Handler error: {e}")
            raise
