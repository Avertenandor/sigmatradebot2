"""Ban Middleware - Block banned users."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from loguru import logger


class BanMiddleware(BaseMiddleware):
    """
    Middleware to block banned users.

    Prevents banned users from interacting with the bot.
    """

    async def __call__(  # noqa: C901
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Process update and check if user is banned.

        Args:
            handler: Next handler
            event: Telegram event
            data: Handler data

        Returns:
            Handler result or None if banned
        """
        # Get user from event
        user: User = data.get("event_from_user")

        if not user:
            return await handler(event, data)

        # Get database session
        session = data.get("session")

        if not session:
            logger.warning("No database session in middleware data")
            return await handler(event, data)

        # Check if user is banned or blacklisted
        # (import here to avoid circular dependency)
        from app.models.blacklist import BlacklistActionType
        from app.repositories.blacklist_repository import BlacklistRepository
        from app.repositories.user_repository import UserRepository

        user_repo = UserRepository(session)
        db_user = await user_repo.get_by_telegram_id(user.id)

        # Check blacklist for non-registered users (registration denial)
        blacklist_repo = BlacklistRepository(session)
        blacklist_entry = await blacklist_repo.get_by_telegram_id(user.id)

        # Pass blacklist_entry to handlers to avoid repeated queries
        data["blacklist_entry"] = blacklist_entry

        if blacklist_entry and blacklist_entry.is_active:
            # For terminated users, block completely (all update types)
            if blacklist_entry.action_type == BlacklistActionType.TERMINATED:
                from app.utils.security_logging import log_security_event

                log_security_event(
                    "Terminated user attempted to use bot",
                    {"telegram_id": user.id}
                )
                return None

            # For blocked users, only allow appeal-related actions
            if blacklist_entry.action_type == BlacklistActionType.BLOCKED:
                from aiogram.types import CallbackQuery, Message

                # Allow /start for BLOCKED users to show menu "
                # "with appeal button
                if (
                    isinstance(event, Message)
                    and event.text
                    and event.text.startswith("/start")
                ):
                    return await handler(event, data)

                # Allow appeal button click
                if (
                    isinstance(event, Message)
                    and event.text == "📝 Подать апелляцию"
                ):
                    return await handler(event, data)

                # Allow appeal callback queries
                if (
                    isinstance(event, CallbackQuery)
                    and event.data
                    and "appeal" in event.data.lower()
                ):
                    return await handler(event, data)

                # Block all other interactions for blocked users
                from app.utils.security_logging import log_security_event

                action_text = (
                    event.text if hasattr(event, "text") and event.text
                    else "callback" if hasattr(event, "data") else "unknown"
                )
                log_security_event(
                    "Blocked user attempted non-appeal action",
                    {
                        "telegram_id": user.id,
                        "action": action_text,
                    }
                )
                return None

        # Check if user is banned (legacy is_banned flag)
        if db_user and db_user.is_banned:
            logger.info(f"Banned user attempted to use bot: {user.id}")
            # Check if user is blocked (can appeal) or terminated (cannot)
            if (
                blacklist_entry
                and blacklist_entry.is_active
                and blacklist_entry.action_type == BlacklistActionType.BLOCKED
            ):
                # Allow appeal
                from aiogram.types import CallbackQuery, Message

                if (
                    isinstance(event, Message)
                    and event.text == "📝 Подать апелляцию"
                ):
                    return await handler(event, data)

                if (
                    isinstance(event, CallbackQuery)
                    and event.data
                    and "appeal" in event.data.lower()
                ):
                    return await handler(event, data)

            # Silently ignore (don't respond to banned/terminated users)
            return None

        # User not banned, continue
        return await handler(event, data)
