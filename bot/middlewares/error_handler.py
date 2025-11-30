"""
Global Error Handler Middleware.

Catches unhandled exceptions and notifies admins.
Sends friendly message to users - never shows technical details.
"""

import traceback
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, TelegramObject
from loguru import logger

from app.config.settings import settings


class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Global error handler middleware.

    - Logs all exceptions
    - Notifies admins with technical details
    - Sends friendly message to user (no technical info!)
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

            bot: Bot | None = data.get("bot")

            # 1. Send friendly message to user (NO technical details!)
            if bot and isinstance(event, Message) and event.from_user:
                try:
                    await bot.send_message(
                        chat_id=event.from_user.id,
                        text=(
                            "❌ Произошла временная ошибка.\n\n"
                            "Администраторы уже уведомлены и работают над решением.\n"
                            "Пожалуйста, попробуйте позже или обратитесь в поддержку."
                        ),
                    )
                except Exception as user_notify_error:
                    logger.warning(f"Failed to notify user: {user_notify_error}")

            # 2. Notify admins with technical details
            admin_ids = settings.get_admin_ids()
            if bot and admin_ids:
                try:
                    error_trace = traceback.format_exc()[-800:]  # Last 800 chars

                    # Get user info for context
                    user_info = "Unknown"
                    if isinstance(event, Message) and event.from_user:
                        user_info = (
                            f"@{event.from_user.username}"
                            if event.from_user.username
                            else f"ID: {event.from_user.id}"
                        )

                    text = (
                        f"🚨 **CRITICAL ERROR**\n\n"
                        f"👤 User: {user_info}\n"
                        f"❌ Exception: `{type(e).__name__}`\n"
                        f"📝 Message: `{str(e)[:200]}`\n\n"
                        f"```\n{error_trace}\n```"
                    )
                    # Notify first admin only (to avoid spam)
                    await bot.send_message(
                        chat_id=admin_ids[0],
                        text=text[:4096],
                        parse_mode="Markdown",
                    )
                except Exception as notify_error:
                    logger.error(f"Failed to notify admin: {notify_error}")

            # Return None to prevent crash
            return None

