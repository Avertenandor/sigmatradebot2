"""
E2E tests for DDoS protection scenarios.

Tests rate limiting under high load conditions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, User as TelegramUser
from bot.middlewares.rate_limit_middleware import RateLimitMiddleware
from bot.utils.operation_rate_limit import OperationRateLimiter


@pytest.mark.security
@pytest.mark.asyncio
async def test_rate_limit_middleware_blocks_excessive_requests() -> None:
    """
    Test that RateLimitMiddleware blocks requests exceeding 30/minute.

    Scenario:
    1. User makes 31 requests in 1 minute
    2. First 30 should pass, 31st should be blocked
    """
    # Create mock Redis
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="30")  # At limit
    mock_redis.incr = AsyncMock(return_value=31)
    mock_redis.expire = AsyncMock()

    # Create middleware
    middleware = RateLimitMiddleware(
        redis_client=mock_redis,
        user_limit=30,
        user_window=60,
    )

    # Create mock handler
    handler_called = False

    async def mock_handler(event, data):
        nonlocal handler_called
        handler_called = True
        return "ok"

    # Create mock event
    telegram_user = TelegramUser(
        id=123456789, is_bot=False, first_name="Test"
    )
    message = Message(
        message_id=1,
        date=1234567890,
        chat=MagicMock(id=123456789),
        from_user=telegram_user,
        text="/start",
    )

    data = {
        "event_from_user": telegram_user,
        "redis_client": mock_redis,
    }

    # Call middleware (should block at limit)
    result = await middleware(mock_handler, message, data)

    # Handler should not be called
    assert handler_called is False, "Handler should not be called when rate limited"
    assert result is None, "Middleware should return None when rate limited"


@pytest.mark.security
@pytest.mark.asyncio
async def test_withdrawal_rate_limit_blocks_excessive_withdrawals() -> None:
    """
    Test that withdrawal rate limit blocks excessive withdrawal requests.

    Scenario:
    1. User makes 10 withdrawal requests in 1 day (should be allowed)
    2. User makes 11th request (should be blocked by daily limit)
    3. User makes 3 withdrawal requests in 1 hour (should be allowed)
    4. User makes 4th request in same hour (should be blocked by hourly limit)
    """
    # Create mock Redis
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # Start fresh
    mock_redis.setex = AsyncMock()

    limiter = OperationRateLimiter(redis_client=mock_redis)

    telegram_id = 123456789

    # Test daily limit (10 per day)
    # Simulate 10 withdrawals already made
    mock_redis.get = AsyncMock(return_value="10")  # At daily limit
    allowed, error = await limiter.check_withdrawal_limit(telegram_id)
    assert allowed is False, "Should be blocked at daily limit (10/day)"
    assert "дневной" in error.lower() or "день" in error.lower(), "Error should mention daily limit"

    # Test hourly limit (3 per hour)
    # Simulate daily OK, but hourly at limit
    mock_redis.get = AsyncMock(side_effect=["0", "3"])  # Daily OK, hourly at limit
    allowed, error = await limiter.check_withdrawal_limit(telegram_id)
    assert allowed is False, "Should be blocked at hourly limit (3/hour)"
    assert "часовой" in error.lower() or "час" in error.lower(), "Error should mention hourly limit"


@pytest.mark.security
@pytest.mark.asyncio
async def test_rate_limiter_fail_open_on_redis_unavailable() -> None:
    """
    Test that rate limiters fail open when Redis is unavailable.

    Scenario:
    1. Redis is unavailable (None or raises errors)
    2. All operations should be allowed (fail open)
    """
    # Test with None Redis
    limiter = OperationRateLimiter(redis_client=None)

    telegram_id = 123456789

    # All operations should be allowed
    allowed, error = await limiter.check_registration_limit(telegram_id)
    assert allowed is True, "Should allow when Redis is None"

    allowed, error = await limiter.check_verification_limit(telegram_id)
    assert allowed is True, "Should allow when Redis is None"

    allowed, error = await limiter.check_withdrawal_limit(telegram_id)
    assert allowed is True, "Should allow when Redis is None"

    # Test with Redis that raises errors
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=Exception("Connection error"))
    mock_redis.setex = AsyncMock(side_effect=Exception("Connection error"))

    limiter = OperationRateLimiter(redis_client=mock_redis)

    # All operations should still be allowed (fail open)
    allowed, error = await limiter.check_registration_limit(telegram_id)
    assert allowed is True, "Should allow on Redis error (fail open)"

