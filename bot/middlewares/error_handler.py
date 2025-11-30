"""
Global Error Handler Middleware.

Catches unhandled exceptions and notifies admins.
"""

import traceback
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.types import ErrorEvent, TelegramObject, Update
from loguru import logger

from app.config.settings import settings


class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Global error handler middleware.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Execute middleware."""
        try:
            return await handler(event, data)
        except Exception as e:
            # Log error
            logger.exception(f"Unhandled exception: {e}")
            
            # Notify super admin if configured
            # Assuming bot instance is in data or accessible
            bot: Bot = data.get("bot")
            if bot and settings.super_admin_id:
                try:
                    error_trace = traceback.format_exc()[-1000:]  # Last 1000 chars
                    text = (
                        f"🚨 **CRITICAL ERROR**\n\n"
                        f"Exception: `{type(e).__name__}: {e}`\n"
                        f"Update: `{event}`\n\n"
                        f"Traceback:\n`{error_trace}`"
                    )
                    await bot.send_message(
                        chat_id=settings.super_admin_id,
                        text=text[:4096],  # Telegram limit
                        parse_mode="Markdown",
                    )
                except Exception as notify_error:
                    logger.error(f"Failed to notify admin: {notify_error}")
            
            # Re-raise to let aiogram know or handle gracefully?
            # Usually we swallow to prevent crash, but log it.
            return None

