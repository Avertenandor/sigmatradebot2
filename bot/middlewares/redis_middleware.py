"""
Redis middleware.

Provides Redis client to handlers for rate limiting and caching.

R11-2: Handles Redis failures with graceful degradation.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from loguru import logger

try:
    import redis.asyncio as redis
    from redis.exceptions import (
        ConnectionError,
        TimeoutError,
        RedisError,
    )
except ImportError:
    redis = None  # type: ignore
    ConnectionError = Exception  # type: ignore
    TimeoutError = Exception  # type: ignore
    RedisError = Exception  # type: ignore


class RedisMiddleware(BaseMiddleware):
    """
    Redis middleware - provides Redis client to handlers.
    
    R11-2: Handles Redis failures gracefully, allowing system to continue
    without Redis (degraded mode).
    
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
        self._redis_healthy = True  # Track Redis health status

    async def _check_redis_health(self) -> bool:
        """
        Check if Redis is healthy.

        R11-2: Performs health check on Redis connection.

        Returns:
            True if Redis is healthy, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            await self.redis_client.ping()
            if not self._redis_healthy:
                # Redis recovered - trigger recovery process
                logger.info("R11-3: Redis connection recovered, triggering recovery")
                self._redis_healthy = True
                # Trigger recovery task asynchronously
                try:
                    from jobs.tasks.redis_recovery import recover_redis_data
                    from jobs.tasks.warmup_redis_cache import warmup_redis_cache

                    # Start recovery and warmup tasks
                    recover_redis_data.send()
                    warmup_redis_cache.send()
                    logger.info("R11-3: Recovery tasks triggered")
                except Exception as recovery_error:
                    logger.warning(
                        f"R11-3: Failed to trigger recovery tasks: {recovery_error}"
                    )
            return True
        except (ConnectionError, TimeoutError, RedisError) as e:
            if self._redis_healthy:
                # Redis just failed
                logger.warning(
                    f"Redis connection lost: {e}. "
                    "System will continue in degraded mode."
                )
                self._redis_healthy = False
            return False
        except Exception as e:
            logger.error(f"Unexpected Redis error during health check: {e}")
            self._redis_healthy = False
            return False

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Provide Redis client to handler with error handling.

        R11-2: Gracefully handles Redis failures.

        Args:
            handler: Next handler
            event: Telegram event
            data: Handler data

        Returns:
            Handler result
        """
        # Check Redis health periodically (every 10th call to avoid overhead)
        # Or check if we know Redis is unhealthy
        if not self._redis_healthy or (hasattr(self, "_check_counter") and self._check_counter % 10 == 0):
            await self._check_redis_health()
            if not hasattr(self, "_check_counter"):
                self._check_counter = 0
            self._check_counter += 1

        # Provide Redis client only if healthy
        if self.redis_client and self._redis_healthy:
            try:
                data["redis_client"] = self.redis_client
            except (ConnectionError, TimeoutError, RedisError) as e:
                # Redis failed during access
                logger.warning(
                    f"Redis error in middleware: {e}. "
                    "Continuing without Redis (degraded mode)."
                )
                self._redis_healthy = False
                # Don't add redis_client to data - handlers will handle None
        else:
            # Redis not available or unhealthy
            # Handlers should check for redis_client existence
            pass
        
        return await handler(event, data)

