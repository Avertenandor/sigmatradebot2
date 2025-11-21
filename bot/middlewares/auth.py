"""
Auth middleware.

Checks if user is registered and loads user data.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthMiddleware(BaseMiddleware):
    """
    Auth middleware.

    Loads user from database and adds to handler data.
    """

    def __init__(self, require_registration: bool = False) -> None:
        """
        Initialize auth middleware.

        Args:
            require_registration: If True, blocks unregistered users
        """
        super().__init__()
        self.require_registration = require_registration

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Load user and check registration.

        Args:
            handler: Next handler
            event: Telegram event
            data: Handler data

        Returns:
            Handler result
        """
        # Get session from data (provided by DatabaseMiddleware)
        session: AsyncSession = data.get("session")
        if not session:
            logger.error("No session in data - DatabaseMiddleware missing?")
            return await handler(event, data)

        # Get telegram user - try from data first (set by aiogram), then from event
        logger.debug(
            f"AuthMiddleware: Checking for telegram_user. Event type: {type(event).__name__}, "
            f"data keys: {list(data.keys())}"
        )

        telegram_user = data.get("event_from_user")
        logger.debug(
            f"AuthMiddleware: event_from_user from data: {telegram_user}, "
            f"type: {type(telegram_user).__name__ if telegram_user else 'None'}"
        )

        if not telegram_user:
            # Fallback: try to get from event directly
            logger.debug("AuthMiddleware: Trying to get from event directly")
            if isinstance(event, Message):
                telegram_user = event.from_user
                logger.debug(f"AuthMiddleware: Message.from_user: {telegram_user}")
            elif isinstance(event, CallbackQuery):
                telegram_user = event.from_user
                logger.debug(f"AuthMiddleware: CallbackQuery.from_user: {telegram_user}")

        if not telegram_user:
            # No user in event, skip
            logger.warning(
                f"AuthMiddleware: No telegram_user found. Event type: {type(event).__name__}, "
                f"data keys: {list(data.keys())}, event_from_user in data: {'event_from_user' in data}"
            )
            return await handler(event, data)

        logger.debug(
            f"AuthMiddleware: Processing event for user {telegram_user.id} (@{telegram_user.username})"
        )

        # Load user from database
        user_repo = UserRepository(session)
        users = await user_repo.find_by(telegram_id=telegram_user.id)
        user: User | None = users[0] if users else None

        # Do NOT auto-create user - registration must be explicit
        # If user not found, set user=None to allow registration flow
        if not user:
            logger.info(
                f"User not found for Telegram ID {telegram_user.id} "
                f"(@{telegram_user.username}) - will show registration menu"
            )

        # Add user to data (may be None for unregistered users)
        data["user"] = user

        # Add user_id, telegram_id for handlers
        if user:
            data["user_id"] = user.id
        else:
            data["user_id"] = None
        data["telegram_id"] = telegram_user.id

        # Check if user is admin
        # Admin check: check Admin table first (authoritative source)
        # This works even if user=None (admin can exist before user registration)
        is_admin = False
        from app.repositories.admin_repository import AdminRepository

        admin_repo = AdminRepository(session)
        admin = await admin_repo.get_by_telegram_id(telegram_user.id)
        if admin is not None:
            # R10-3: Check if admin is blocked
            if admin.is_blocked:
                logger.warning(
                    f"R10-3: Blocked admin {admin.id} (telegram_id={telegram_user.id}) "
                    f"attempted to access system"
                )
                is_admin = False
                admin = None  # Don't expose blocked admin
            else:
                is_admin = True
                logger.info(
                    f"User {telegram_user.id} (@{telegram_user.username}) "
                    f"identified as admin from Admin table (role: {admin.role if admin else 'unknown'})"
                )
        else:
            logger.debug(
                f"User {telegram_user.id} is not an admin "
                f"(not in Admin table, user={'exists' if user else 'None'})"
            )

        # Store admin object and admin_id
        # Admin rights come ONLY from Admin table, not from user.is_admin flag
        data["is_admin"] = is_admin
        data["admin"] = admin if admin else None
        data["admin_id"] = admin.id if admin else 0
        logger.info(
            f"AuthMiddleware: Set is_admin={is_admin}, admin_id={data['admin_id']} for user {telegram_user.id}"
        )

        # Call next handler
        return await handler(event, data)
