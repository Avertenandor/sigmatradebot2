"""
Operation Rate Limiter.

Provides per-operation rate limiting for critical actions:
- Registration
- Verification
- Withdrawal requests
"""

from typing import Any

from loguru import logger


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
            return True, None  # No Redis, allow

        try:
            # Check daily limit (20 per day)
            daily_key = f"op_limit:withdraw:day:{telegram_id}"
            daily_count_str = await self.redis_client.get(daily_key)
            daily_count = int(daily_count_str) if daily_count_str else 0

            if daily_count >= 20:
                return (
                    False,
                    "Превышен дневной лимит заявок на вывод (20/день). "
                    "Попробуйте завтра.",
                )

            # Check hourly limit (10 per hour)
            hourly_key = f"op_limit:withdraw:hour:{telegram_id}"
            hourly_count_str = await self.redis_client.get(hourly_key)
            hourly_count = int(hourly_count_str) if hourly_count_str else 0

            if hourly_count >= 10:
                return (
                    False,
                    "Превышен часовой лимит заявок на вывод (10/час). "
                    "Попробуйте позже.",
                )

            # Increment counters
            await self.redis_client.setex(
                daily_key, 86400, str(daily_count + 1)
            )  # 24 hours
            await self.redis_client.setex(
                hourly_key, 3600, str(hourly_count + 1)
            )  # 1 hour

            return True, None

        except Exception as e:
            logger.error(f"Error checking withdrawal limit: {e}")
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
            return True, None  # No Redis, allow

        try:
            key = f"op_limit:{operation}:{telegram_id}"

            # Get current count
            count_str = await self.redis_client.get(key)
            count = int(count_str) if count_str else 0

            # Check limit
            if count >= max_attempts:
                minutes = window_seconds // 60
                return (
                    False,
                    f"Слишком много попыток {operation_name}. "
                    f"Лимит: {max_attempts} попыток за {minutes} минут. "
                    f"Попробуйте позже.",
                )

            # Increment counter
            await self.redis_client.setex(
                key, window_seconds, str(count + 1)
            )

            return True, None

        except Exception as e:
            logger.error(f"Error checking {operation} limit: {e}")
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

