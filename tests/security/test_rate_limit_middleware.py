"""
Tests for RateLimitMiddleware and OperationRateLimiter.

Tests that rate limiting works correctly to prevent spam and abuse.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, User as TelegramUser

from bot.middlewares.rate_limit_middleware import RateLimitMiddleware
from bot.utils.operation_rate_limit import OperationRateLimiter


@pytest.mark.security
@pytest.mark.asyncio
async def test_rate_limit_middleware_blocks_after_limit() -> None:
    """
    Test that 31st update in a minute is blocked.
    
    Scenario:
    1. Create middleware with limit=30, window=60
    2. Process 30 messages (all should pass)
    3. Process 31st message (should return None, handler not called)
    """
    # Create mock Redis
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_redis.incr = AsyncMock()
    
    # Create middleware
    middleware = RateLimitMiddleware(
        redis_client=mock_redis,
        user_limit=30,
        user_window=60,
    )
    
    # Create message
    message = Message(
        from_user=TelegramUser(
            id=123456789,
            is_bot=False,
            first_name="Test",
        ),
        text="/start",
        message_id=1,
        date=None,
        chat=None,
    )
    
    # Track handler calls
    handler_called = []
    
    async def mock_handler(event, data):
        handler_called.append(True)
        return "handled"
    
    # Process 30 messages (should all pass)
    for i in range(30):
        data = {
            "event_from_user": message.from_user,
        }
        # Simulate incrementing counter
        if i == 0:
            mock_redis.get.return_value = None
        else:
            mock_redis.get.return_value = str(i)
        
        result = await middleware(mock_handler, message, data)
        assert result == "handled", f"Message {i+1} should be handled"
    
    # 31st message should be blocked
    mock_redis.get.return_value = "30"  # At limit
    data = {
        "event_from_user": message.from_user,
    }
    result = await middleware(mock_handler, message, data)
    assert result is None, "31st message should be blocked (return None)"
    assert len(handler_called) == 30, "Handler should be called only 30 times"


@pytest.mark.security
@pytest.mark.asyncio
async def test_rate_limit_middleware_fail_open_on_redis_error() -> None:
    """
    Test that middleware allows requests when Redis is unavailable (fail-open).
    
    Scenario:
    1. Redis raises exception
    2. Process message
    3. Verify: message is allowed (handler called)
    """
    # Create mock Redis that raises exception
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=Exception("Redis connection failed"))
    
    # Create middleware
    middleware = RateLimitMiddleware(
        redis_client=mock_redis,
        user_limit=30,
        user_window=60,
    )
    
    # Create message
    message = Message(
        from_user=TelegramUser(
            id=123456789,
            is_bot=False,
            first_name="Test",
        ),
        text="/start",
        message_id=1,
        date=None,
        chat=None,
    )
    
    handler_called = []
    
    async def mock_handler(event, data):
        handler_called.append(True)
        return "handled"
    
    # Process message (should pass despite Redis error)
    data = {
        "event_from_user": message.from_user,
    }
    result = await middleware(mock_handler, message, data)
    
    assert result == "handled", "Message should be allowed on Redis error (fail-open)"
    assert len(handler_called) == 1, "Handler should be called"


@pytest.mark.security
@pytest.mark.asyncio
async def test_operation_rate_limiter_blocks_registration_after_limit() -> None:
    """
    Test that OperationRateLimiter blocks registration after limit.
    
    Scenario:
    1. Create limiter with limit=3, window=3600
    2. Make 3 registration attempts (allowed)
    3. Make 4th attempt (blocked)
    """
    # Create mock Redis
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock()
    
    limiter = OperationRateLimiter(
        redis_client=mock_redis,
        limit=3,
        window_seconds=3600,
        operation_name="registration",
    )
    
    user_id = 123456789
    
    # First 3 attempts should not be limited
    for i in range(3):
        mock_redis.get.return_value = str(i)
        is_limited = await limiter.is_limited(user_id)
        assert is_limited is False, f"Attempt {i+1} should be allowed"
        await limiter.increment(user_id)
    
    # 4th attempt should be limited
    mock_redis.get.return_value = "3"
    is_limited = await limiter.is_limited(user_id)
    assert is_limited is True, "4th attempt should be blocked"


@pytest.mark.security
@pytest.mark.asyncio
async def test_operation_rate_limiter_blocks_withdrawal_after_limit() -> None:
    """
    Test that OperationRateLimiter blocks withdrawal after limit.
    
    Scenario:
    1. Create limiter for withdrawals with limit=3, window=3600
    2. Make 3 withdrawal attempts (allowed)
    3. Make 4th attempt (blocked)
    """
    # Create mock Redis
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock()
    
    limiter = OperationRateLimiter(
        redis_client=mock_redis,
        limit=3,
        window_seconds=3600,
        operation_name="withdrawal_hourly",
    )
    
    user_id = 123456789
    
    # First 3 attempts should not be limited
    for i in range(3):
        mock_redis.get.return_value = str(i)
        is_limited = await limiter.is_limited(user_id)
        assert is_limited is False, f"Withdrawal attempt {i+1} should be allowed"
        await limiter.increment(user_id)
    
    # 4th attempt should be limited
    mock_redis.get.return_value = "3"
    is_limited = await limiter.is_limited(user_id)
    assert is_limited is True, "4th withdrawal attempt should be blocked"


@pytest.mark.security
@pytest.mark.asyncio
async def test_operation_rate_limiter_fail_open_on_redis_error() -> None:
    """
    Test that OperationRateLimiter allows operations when Redis is unavailable.
    
    Scenario:
    1. Redis raises exception
    2. Check if limited
    3. Verify: returns False (not limited, fail-open)
    """
    # Create mock Redis that raises exception
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=Exception("Redis connection failed"))
    
    limiter = OperationRateLimiter(
        redis_client=mock_redis,
        limit=3,
        window_seconds=3600,
        operation_name="registration",
    )
    
    # Check if limited (should return False on error - fail-open)
    is_limited = await limiter.is_limited(123456789)
    assert is_limited is False, "Should not be limited on Redis error (fail-open)"

