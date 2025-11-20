"""
Tests for OperationRateLimiter.

Tests that operation rate limits work correctly.
"""

import pytest
from unittest.mock import AsyncMock
from bot.utils.operation_rate_limit import OperationRateLimiter


@pytest.mark.security
@pytest.mark.asyncio
async def test_registration_rate_limit() -> None:
    """
    Test registration rate limit (3 attempts per hour).

    Scenario:
    1. Make 3 registration attempts (should be allowed)
    2. Make 4th attempt (should be blocked)
    """
    # Create mock Redis
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # Start with no count
    mock_redis.setex = AsyncMock()

    limiter = OperationRateLimiter(redis_client=mock_redis)

    telegram_id = 123456789

    # First 3 attempts should succeed
    for i in range(3):
        allowed, error = await limiter.check_registration_limit(telegram_id)
        assert allowed is True, f"Attempt {i+1} should be allowed"
        assert error is None, f"Attempt {i+1} should have no error"

    # Simulate that we've reached the limit
    mock_redis.get = AsyncMock(return_value="3")  # At limit

    # 4th attempt should fail
    allowed, error = await limiter.check_registration_limit(telegram_id)
    assert allowed is False, "4th attempt should be blocked"
    assert error is not None, "Should return error message"
    assert "регистрация" in error.lower(), "Error should mention registration"


@pytest.mark.security
@pytest.mark.asyncio
async def test_verification_rate_limit() -> None:
    """
    Test verification rate limit (5 attempts per hour).

    Scenario:
    1. Make 5 verification attempts (should be allowed)
    2. Make 6th attempt (should be blocked)
    """
    # Create mock Redis
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # Start with no count
    mock_redis.setex = AsyncMock()

    limiter = OperationRateLimiter(redis_client=mock_redis)

    telegram_id = 123456789

    # First 5 attempts should succeed
    for i in range(5):
        allowed, error = await limiter.check_verification_limit(telegram_id)
        assert allowed is True, f"Attempt {i+1} should be allowed"
        assert error is None, f"Attempt {i+1} should have no error"

    # Simulate that we've reached the limit
    mock_redis.get = AsyncMock(return_value="5")  # At limit

    # 6th attempt should fail
    allowed, error = await limiter.check_verification_limit(telegram_id)
    assert allowed is False, "6th attempt should be blocked"
    assert error is not None, "Should return error message"
    assert "верификация" in error.lower(), "Error should mention verification"


@pytest.mark.security
@pytest.mark.asyncio
async def test_withdrawal_rate_limit() -> None:
    """
    Test withdrawal rate limit (10 per day, 3 per hour).

    Scenario:
    1. Check daily limit (10 per day)
    2. Check hourly limit (3 per hour)
    """
    # Create mock Redis
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # Start with no count
    mock_redis.setex = AsyncMock()

    limiter = OperationRateLimiter(redis_client=mock_redis)

    telegram_id = 123456789

    # Test daily limit
    mock_redis.get = AsyncMock(return_value="10")  # At daily limit
    allowed, error = await limiter.check_withdrawal_limit(telegram_id)
    assert allowed is False, "Should be blocked at daily limit"
    assert error is not None, "Should return error message"
    assert "дневной" in error.lower() or "день" in error.lower(), "Error should mention daily limit"

    # Test hourly limit
    mock_redis.get = AsyncMock(side_effect=["0", "3"])  # Daily OK, hourly at limit
    allowed, error = await limiter.check_withdrawal_limit(telegram_id)
    assert allowed is False, "Should be blocked at hourly limit"
    assert error is not None, "Should return error message"
    assert "часовой" in error.lower() or "час" in error.lower(), "Error should mention hourly limit"


@pytest.mark.security
@pytest.mark.asyncio
async def test_rate_limiter_fail_open_without_redis() -> None:
    """
    Test that rate limiter fails open (allows) when Redis is unavailable.

    Scenario:
    1. Create rate limiter without Redis client
    2. Check limits
    3. Verify returns True (allowed) - fail open
    """
    limiter = OperationRateLimiter(redis_client=None)

    telegram_id = 123456789

    # All checks should allow when no Redis
    allowed, error = await limiter.check_registration_limit(telegram_id)
    assert allowed is True, "Should fail open (allow) when Redis unavailable"
    assert error is None, "Should have no error when Redis unavailable"

    allowed, error = await limiter.check_verification_limit(telegram_id)
    assert allowed is True, "Should fail open (allow) when Redis unavailable"

    allowed, error = await limiter.check_withdrawal_limit(telegram_id)
    assert allowed is True, "Should fail open (allow) when Redis unavailable"


@pytest.mark.security
@pytest.mark.asyncio
async def test_rate_limiter_redis_error_handling() -> None:
    """
    Test that rate limiter handles Redis errors gracefully (fail open).

    Scenario:
    1. Create rate limiter with Redis that raises errors
    2. Check limits
    3. Verify returns True (allowed) - fail open on error
    """
    # Create mock Redis that raises errors
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=Exception("Redis connection error"))
    mock_redis.setex = AsyncMock(side_effect=Exception("Redis connection error"))

    limiter = OperationRateLimiter(redis_client=mock_redis)

    telegram_id = 123456789

    # All checks should allow when Redis errors
    allowed, error = await limiter.check_registration_limit(telegram_id)
    assert allowed is True, "Should fail open (allow) on Redis error"
    assert error is None, "Should have no error on Redis error"
