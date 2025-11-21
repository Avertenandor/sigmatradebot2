"""
Rate Limit Middleware - Prevent spam and abuse.

R11-2: Uses in-memory counters as fallback when Redis is unavailable.
"""

from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from loguru import logger

try:
    import redis.asyncio as redis
except ImportError:
    redis = None  # type: ignore


class RateLimitMiddleware(BaseMiddleware):
    """
    Rate limiting middleware.

    Limits:
    - Per-user: 30 requests per minute
    - Per-IP: 100 requests per minute (if available)
    """

    def __init__(
        self,
        redis_client: Any | None = None,
        user_limit: int = 30,
        user_window: int = 60,
    ) -> None:
        """
        Initialize rate limit middleware.

        Args:
            redis_client: Redis client (optional)
            user_limit: Max requests per user
            user_window: Time window in seconds
        """
        super().__init__()
        self.redis_client = redis_client
        self.user_limit = user_limit
        self.user_window = user_window
        
        # R11-2: In-memory fallback counters
        # Structure: {user_id: [(timestamp, ...), ...]}
        self._user_counts: dict[int, list[datetime]] = defaultdict(list)

    def _cleanup_old_entries(self, user_id: int) -> None:
        """
        Clean up old entries from in-memory counter.

        R11-2: Removes entries older than the time window.

        Args:
            user_id: User ID
        """
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=self.user_window)
        self._user_counts[user_id] = [
            ts for ts in self._user_counts[user_id] if ts > cutoff
        ]

    def _check_in_memory_limit(self, user_id: int) -> bool:
        """
        Check rate limit using in-memory counters.

        R11-2: Fallback when Redis is unavailable.

        Args:
            user_id: User ID

        Returns:
            True if within limit, False if exceeded
        """
        self._cleanup_old_entries(user_id)
        count = len(self._user_counts[user_id])
        
        if count >= self.user_limit:
            return False
        
        # Add current request
        self._user_counts[user_id].append(datetime.now(UTC))
        return True

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]], Awaitable[Any]
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Check rate limit and process update.

        R11-2: Uses Redis when available, falls back to in-memory counters.
        """
        user: User = data.get("event_from_user")

        if not user:
            return await handler(event, data)

        # Try Redis first
        if self.redis_client:
            try:
                # Rate limit key
                key = f"ratelimit:user:{user.id}"

                # Get current count
                count = await self.redis_client.get(key)

                if count is None:
                    # First request in window
                    await self.redis_client.setex(
                        key, self.user_window, "1"
                    )
                    return await handler(event, data)

                current_count = int(count)

                if current_count >= self.user_limit:
                    logger.warning(
                        f"R11-2: Rate limit exceeded for user {user.id}: "
                        f"{current_count}/{self.user_limit}"
                    )
                    # Silently ignore (don't waste resources responding)
                    return None

                # Increment counter
                await self.redis_client.incr(key)
                return await handler(event, data)

            except Exception as e:
                # R11-2: Redis failed, fall back to in-memory
                logger.warning(
                    f"R11-2: Redis error in rate limit, using in-memory fallback: {e}"
                )

        # R11-2: Fallback to in-memory counters
        if not self._check_in_memory_limit(user.id):
            logger.warning(
                f"R11-2: Rate limit exceeded for user {user.id} "
                f"(in-memory fallback): {len(self._user_counts[user.id])}/{self.user_limit}"
            )
            # Silently ignore (don't waste resources responding)
            return None

        return await handler(event, data)
