"""
Global Error Handler Middleware.

Catches unhandled exceptions and notifies admins.
"""

import traceback
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject
from loguru import logger

from app.config.settings import settings


class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Global error handler middleware.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Execute middleware."""
        try:
            return await handler(event, data)
        except Exception as e:
            # Log error
            logger.exception(f"Unhandled exception: {e}")
            
            # Get admin IDs from settings
            admin_ids = settings.get_admin_ids()
            
            # Notify first admin if configured
            bot: Bot | None = data.get("bot")
            if bot and admin_ids:
                try:
                    error_trace = traceback.format_exc()[-800:]  # Last 800 chars
                    text = (
                        f"🚨 **CRITICAL ERROR**\n\n"
                        f"Exception: `{type(e).__name__}`\n"
                        f"Message: `{str(e)[:200]}`\n\n"
                        f"Traceback:\n```\n{error_trace}\n```"
                    )
                    # Notify first admin
                    await bot.send_message(
                        chat_id=admin_ids[0],
                        text=text[:4096],
                        parse_mode="Markdown",
                    )
                except Exception as notify_error:
                    logger.error(f"Failed to notify admin: {notify_error}")
            
            # Return None to prevent crash
            return None

