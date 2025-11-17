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
        logger.info(
            f"AuthMiddleware: Checking for telegram_user. Event type: {type(event).__name__}, "
            f"data keys: {list(data.keys())}"
        )
        
        telegram_user = data.get("event_from_user")
        logger.info(
            f"AuthMiddleware: event_from_user from data: {telegram_user}, "
            f"type: {type(telegram_user).__name__ if telegram_user else 'None'}"
        )
        
        if not telegram_user:
            # Fallback: try to get from event directly
            logger.info(f"AuthMiddleware: Trying to get from event directly")
            if isinstance(event, Message):
                telegram_user = event.from_user
                logger.info(f"AuthMiddleware: Message.from_user: {telegram_user}")
            elif isinstance(event, CallbackQuery):
                telegram_user = event.from_user
                logger.info(f"AuthMiddleware: CallbackQuery.from_user: {telegram_user}")

        if not telegram_user:
            # No user in event, skip
            logger.warning(
                f"AuthMiddleware: No telegram_user found. Event type: {type(event).__name__}, "
                f"data keys: {list(data.keys())}, event_from_user in data: {'event_from_user' in data}"
            )
            return await handler(event, data)

        logger.info(
            f"AuthMiddleware: Processing event for user {telegram_user.id} (@{telegram_user.username})"
        )

        # Load user from database
        user_repo = UserRepository(session)
        users = await user_repo.find_by(telegram_id=telegram_user.id)
        user: User | None = users[0] if users else None

        # Create user if not exists
        if not user:
            user = await user_repo.create(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
            )
            logger.info(
                f"Auto-created user {user.id} for Telegram ID "
                f"{telegram_user.id} (@{telegram_user.username})"
            )

        # Add user to data
        data["user"] = user

        # Add user_id, telegram_id for handlers
        data["user_id"] = user.id
        data["telegram_id"] = telegram_user.id

        # Check if user is admin
        # Admin check: user.is_admin or check Admin table
        is_admin = False
        if hasattr(user, "is_admin"):
            is_admin = user.is_admin
            logger.debug(
                f"User {telegram_user.id} is_admin from user.is_admin: {is_admin}"
            )
        else:
            # Check if user exists in Admin table
            from app.repositories.admin_repository import AdminRepository

            admin_repo = AdminRepository(session)
            admin = await admin_repo.get_by_telegram_id(telegram_user.id)
            is_admin = admin is not None
            logger.info(
                f"User {telegram_user.id} admin check: admin={admin}, is_admin={is_admin}"
            )
            if is_admin:
                logger.info(
                    f"User {telegram_user.id} (@{telegram_user.username}) "
                    f"identified as admin (role: {admin.role if admin else 'unknown'})"
                )

        data["is_admin"] = is_admin
        data["admin_id"] = user.id if is_admin else 0
        logger.info(
            f"AuthMiddleware: Set is_admin={is_admin}, admin_id={data['admin_id']} for user {telegram_user.id}"
        )

        # Call next handler
        return await handler(event, data)
