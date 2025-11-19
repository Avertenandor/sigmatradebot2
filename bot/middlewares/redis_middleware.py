"""
Redis middleware.

Provides Redis client to handlers for rate limiting and caching.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class RedisMiddleware(BaseMiddleware):
    """
    Redis middleware - provides Redis client to handlers.
    
    Adds redis_client to handler data if available.
    """

    def __init__(self, redis_client: Any | None = None) -> None:
        """
        Initialize Redis middleware.

        Args:
            redis_client: Optional Redis client
        """
        super().__init__()
        self.redis_client = redis_client

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Provide Redis client to handler.

        Args:
            handler: Next handler
            event: Telegram event
            data: Handler data

        Returns:
            Handler result
        """
        if self.redis_client:
            data["redis_client"] = self.redis_client
        
        return await handler(event, data)

