"""
Database middleware.

Provides database session to handlers.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker


class DatabaseMiddleware(BaseMiddleware):
    """Database middleware - provides session to handlers."""

    def __init__(self, session_pool: async_sessionmaker) -> None:
        """
        Initialize database middleware.

        Args:
            session_pool: SQLAlchemy async session maker
        """
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Provide database session to handler.

        Args:
            handler: Next handler
            event: Telegram event
            data: Handler data

        Returns:
            Handler result
        """
        async with self.session_pool() as session:
            # Add session to data
            data["session"] = session

            # Call next handler
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
