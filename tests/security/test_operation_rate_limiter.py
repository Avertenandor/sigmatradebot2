"""
Tests for OperationRateLimiter.

Tests that operation rate limits work correctly.
"""

import pytest
from unittest.mock import AsyncMock
from bot.utils.operation_rate_limit import OperationRateLimiter


@pytest.mark.security
@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_limit() -> None:
    """
    Test that rate limiter blocks operations after limit is exceeded.

    Scenario:
    1. Create rate limiter with limit=3, window=3600
    2. Make 3 operations (should be allowed)
    3. Make 4th operation (should be blocked)
    """
    # Create mock Redis
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "3"  # Already at limit
    mock_redis.incr = AsyncMock()
    mock_redis.expire = AsyncMock()

    limiter = OperationRateLimiter(
        redis_client=mock_redis,
        limit=3,
        window_seconds=3600,
        operation_name="test_operation",
    )

    # Check if limited
    is_limited = await limiter.is_limited(123456789)

    assert is_limited is True, "Should be limited after 3 attempts"


@pytest.mark.security
@pytest.mark.asyncio
async def test_rate_limiter_allows_below_limit() -> None:
    """
    Test that rate limiter allows operations below limit.

    Scenario:
    1. Create rate limiter with limit=3
    2. Make operation when count < limit
    3. Verify operation is allowed
    """
    # Create mock Redis
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "1"  # Below limit
    mock_redis.incr = AsyncMock()
    mock_redis.expire = AsyncMock()

    limiter = OperationRateLimiter(
        redis_client=mock_redis,
        limit=3,
        window_seconds=3600,
        operation_name="test_operation",
    )

    # Check if limited
    is_limited = await limiter.is_limited(123456789)

    assert is_limited is False, "Should not be limited below limit"


@pytest.mark.security
@pytest.mark.asyncio
async def test_rate_limiter_increments_counter() -> None:
    """
    Test that rate limiter increments counter on increment().

    Scenario:
    1. Create rate limiter
    2. Call increment()
    3. Verify Redis incr and expire are called
    """
    # Create mock Redis
    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock()

    limiter = OperationRateLimiter(
        redis_client=mock_redis,
        limit=3,
        window_seconds=3600,
        operation_name="test_operation",
    )

    # Increment
    await limiter.increment(123456789)

    # Verify Redis methods were called
    assert mock_redis.incr.called, "Redis incr should be called"
    assert mock_redis.expire.called, "Redis expire should be called"

    # Verify correct key format
    incr_key = mock_redis.incr.call_args[0][0]
    assert "op_ratelimit" in incr_key
    assert "test_operation" in incr_key
    assert "123456789" in incr_key

    # Verify expire was called with correct TTL
    expire_key = mock_redis.expire.call_args[0][0]
    expire_ttl = mock_redis.expire.call_args[0][1]
    assert expire_key == incr_key
    assert expire_ttl == 3600


@pytest.mark.security
@pytest.mark.asyncio
async def test_rate_limiter_fail_open_without_redis() -> None:
    """
    Test that rate limiter fails open (allows) when Redis is unavailable.

    Scenario:
    1. Create rate limiter without Redis client
    2. Check if limited
    3. Verify returns False (not limited) - fail open
    """
    limiter = OperationRateLimiter(
        redis_client=None,
        limit=3,
        window_seconds=3600,
        operation_name="test_operation",
    )

    # Check if limited (should return False when no Redis)
    is_limited = await limiter.is_limited(123456789)

    assert is_limited is False, "Should fail open (not limit) when Redis unavailable"

