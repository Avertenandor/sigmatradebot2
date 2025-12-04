"""
Operation Rate Limiter.

Provides per-operation rate limiting for critical actions:
- Registration
- Verification
- Withdrawal requests
"""

from typing import Any

from loguru import logger

# Lua script for atomic rate limit check
OPERATION_LIMIT_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, window)
end
return current <= limit and 1 or 0
"""

# Lua script for dual rate limit check (daily + hourly)
WITHDRAWAL_LIMIT_SCRIPT = """
local daily_key = KEYS[1]
local hourly_key = KEYS[2]
local daily_limit = tonumber(ARGV[1])
local hourly_limit = tonumber(ARGV[2])
local daily_window = tonumber(ARGV[3])
local hourly_window = tonumber(ARGV[4])

-- Increment daily counter
local daily_count = redis.call('INCR', daily_key)
if daily_count == 1 then
    redis.call('EXPIRE', daily_key, daily_window)
end

-- Check daily limit
if daily_count > daily_limit then
    -- Decrement back since we exceeded
    redis.call('DECR', daily_key)
    return -1  -- Daily limit exceeded
end

-- Increment hourly counter
local hourly_count = redis.call('INCR', hourly_key)
if hourly_count == 1 then
    redis.call('EXPIRE', hourly_key, hourly_window)
end

-- Check hourly limit
if hourly_count > hourly_limit then
    -- Decrement both back since we exceeded
    redis.call('DECR', daily_key)
    redis.call('DECR', hourly_key)
    return -2  -- Hourly limit exceeded
end

return 1  -- Success
"""


class OperationRateLimiter:
    """
    Rate limiter for critical operations.

    Uses Redis to track attempts per user per operation type.
    """

    def __init__(self, redis_client: Any | None = None) -> None:
        """
        Initialize operation rate limiter.

        Args:
            redis_client: Optional Redis client
        """
        self.redis_client = redis_client

    async def check_registration_limit(
        self, telegram_id: int
    ) -> tuple[bool, str | None]:
        """
        Check if user can register (3 attempts per hour).

        Args:
            telegram_id: Telegram user ID

        Returns:
            Tuple of (allowed, error_message)
        """
        return await self._check_limit(
            operation="reg",
            telegram_id=telegram_id,
            max_attempts=3,
            window_seconds=3600,  # 1 hour
            operation_name="регистрация",
        )

    async def check_verification_limit(
        self, telegram_id: int
    ) -> tuple[bool, str | None]:
        """
        Check if user can verify (5 attempts per hour).

        Args:
            telegram_id: Telegram user ID

        Returns:
            Tuple of (allowed, error_message)
        """
        return await self._check_limit(
            operation="verify",
            telegram_id=telegram_id,
            max_attempts=5,
            window_seconds=3600,  # 1 hour
            operation_name="верификация",
        )

    async def check_withdrawal_limit(
        self, telegram_id: int
    ) -> tuple[bool, str | None]:
        """
        Check if user can create withdrawal request.

        Limits:
        - 20 requests per day
        - 10 requests per hour

        Args:
            telegram_id: Telegram user ID

        Returns:
            Tuple of (allowed, error_message)
        """
        if not self.redis_client:
            logger.warning("Redis unavailable, allowing withdrawal without rate limit check")
            return True, None  # No Redis, allow

        try:
            daily_key = f"op_limit:withdraw:day:{telegram_id}"
            hourly_key = f"op_limit:withdraw:hour:{telegram_id}"

            # Use Lua script for atomic check-and-increment of both limits
            # Returns: 1 = success, -1 = daily exceeded, -2 = hourly exceeded
            result = await self.redis_client.eval(
                WITHDRAWAL_LIMIT_SCRIPT,
                2,  # Number of keys
                daily_key,
                hourly_key,
                20,  # Daily limit
                10,  # Hourly limit
                86400,  # Daily window (24 hours)
                3600,  # Hourly window (1 hour)
            )

            if result == -1:
                return (
                    False,
                    "Превышен дневной лимит заявок на вывод (20/день). "
                    "Попробуйте завтра.",
                )

            if result == -2:
                return (
                    False,
                    "Превышен часовой лимит заявок на вывод (10/час). "
                    "Попробуйте позже.",
                )

            return True, None

        except Exception as e:
            logger.warning(f"Redis error checking withdrawal limit: {e}")
            # Fail open - allow on error
            return True, None

    async def _check_limit(
        self,
        operation: str,
        telegram_id: int,
        max_attempts: int,
        window_seconds: int,
        operation_name: str,
    ) -> tuple[bool, str | None]:
        """
        Check operation rate limit.

        Args:
            operation: Operation type (reg, verify, etc.)
            telegram_id: Telegram user ID
            max_attempts: Maximum attempts allowed
            window_seconds: Time window in seconds
            operation_name: Human-readable operation name

        Returns:
            Tuple of (allowed, error_message)
        """
        if not self.redis_client:
            logger.warning(f"Redis unavailable, allowing {operation} operation without rate limit check")
            return True, None  # No Redis, allow

        try:
            key = f"op_limit:{operation}:{telegram_id}"

            # Use Lua script for atomic check-and-increment
            # Returns 1 if allowed, 0 if limit exceeded
            result = await self.redis_client.eval(
                OPERATION_LIMIT_SCRIPT,
                1,  # Number of keys
                key,
                max_attempts,
                window_seconds,
            )

            if result == 0:
                # Limit exceeded
                minutes = window_seconds // 60
                return (
                    False,
                    f"Слишком много попыток {operation_name}. "
                    f"Лимит: {max_attempts} попыток за {minutes} минут. "
                    f"Попробуйте позже.",
                )

            return True, None

        except Exception as e:
            logger.warning(f"Redis error checking {operation} limit: {e}")
            # Fail open - allow on error
            return True, None

    async def clear_limit(
        self, operation: str, telegram_id: int
    ) -> None:
        """
        Clear rate limit for operation (e.g., on success).

        Args:
            operation: Operation type
            telegram_id: Telegram user ID
        """
        if not self.redis_client:
            return

        try:
            key = f"op_limit:{operation}:{telegram_id}"
            await self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error clearing {operation} limit: {e}")

