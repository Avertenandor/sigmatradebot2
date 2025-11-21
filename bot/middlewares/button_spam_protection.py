"""
Button spam protection middleware.

R13-2: Prevents rapid repeated clicks on the same button.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject
from loguru import logger

try:
    import redis.asyncio as redis
except ImportError:
    redis = None  # type: ignore


class ButtonSpamProtectionMiddleware(BaseMiddleware):
    """
    R13-2: Button spam protection middleware.

    Prevents rapid repeated clicks on the same button by implementing
    cooldown periods per button action.
    """

    # Cooldown periods (in seconds)
    COOLDOWN_NORMAL = 0.5  # 500ms for normal actions
    COOLDOWN_FINANCIAL = 2.0  # 2 seconds for financial actions
    COOLDOWN_CRITICAL = 3.0  # 3 seconds for critical operations

    # Financial action patterns
    FINANCIAL_PATTERNS = [
        "withdrawal",
        "deposit",
        "balance",
        "withdraw",
        "finpass",
        "financial",
    ]

    # Critical action patterns
    CRITICAL_PATTERNS = [
        "confirm",
        "approve",
        "delete",
        "terminate",
        "block",
    ]

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
    ) -> None:
        """
        Initialize button spam protection middleware.

        Args:
            redis_client: Optional Redis client for distributed protection
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
        Check button spam protection and process update.

        R13-2: Implements cooldown for button clicks.

        Args:
            handler: Next handler
            event: Telegram event
            data: Handler data

        Returns:
            Handler result or None if spam detected
        """
        # Only protect callback queries (button clicks)
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)

        user = event.from_user
        if not user:
            return await handler(event, data)

        callback_data = event.data
        if not callback_data:
            return await handler(event, data)

        # Determine cooldown based on action type
        cooldown = self._get_cooldown(callback_data)

        # Check if action is on cooldown
        if await self._is_on_cooldown(user.id, callback_data, cooldown):
            logger.debug(
                f"Button spam protection: user {user.id} clicked "
                f"{callback_data} too soon (cooldown: {cooldown}s)"
            )
            # Answer callback to prevent loading state
            try:
                await event.answer("⏳ Подождите немного", show_alert=False)
            except Exception:
                pass  # Ignore if answer fails
            return None  # Don't process handler

        # Set cooldown
        await self._set_cooldown(user.id, callback_data, cooldown)

        # Process handler
        return await handler(event, data)

    def _get_cooldown(self, callback_data: str) -> float:
        """
        Get cooldown period for callback data.

        Args:
            callback_data: Callback data string

        Returns:
            Cooldown in seconds
        """
        callback_lower = callback_data.lower()

        # Check for critical patterns
        for pattern in self.CRITICAL_PATTERNS:
            if pattern in callback_lower:
                return self.COOLDOWN_CRITICAL

        # Check for financial patterns
        for pattern in self.FINANCIAL_PATTERNS:
            if pattern in callback_lower:
                return self.COOLDOWN_FINANCIAL

        # Default cooldown for normal actions
        return self.COOLDOWN_NORMAL

    async def _is_on_cooldown(
        self, user_id: int, callback_data: str, cooldown: float
    ) -> bool:
        """
        Check if action is on cooldown.

        Args:
            user_id: User ID
            callback_data: Callback data
            cooldown: Cooldown period

        Returns:
            True if on cooldown
        """
        if not self.redis_client:
            # No Redis - use in-memory (not distributed, but works)
            return False

        try:
            key = f"button_cooldown:{user_id}:{callback_data}"
            exists = await self.redis_client.exists(key)
            return exists == 1
        except Exception as e:
            logger.warning(f"Redis error in button spam protection: {e}")
            return False  # Fail open

    async def _set_cooldown(
        self, user_id: int, callback_data: str, cooldown: float
    ) -> None:
        """
        Set cooldown for action.

        Args:
            user_id: User ID
            callback_data: Callback data
            cooldown: Cooldown period
        """
        if not self.redis_client:
            return

        try:
            key = f"button_cooldown:{user_id}:{callback_data}"
            await self.redis_client.setex(key, int(cooldown), "1")
        except Exception as e:
            logger.warning(f"Redis error setting cooldown: {e}")

