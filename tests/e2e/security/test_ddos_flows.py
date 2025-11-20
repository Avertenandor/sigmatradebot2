"""
E2E tests for DDoS protection and rate limiting scenarios.

Tests complete flows of DDoS protection:
1. RateLimitMiddleware blocks spam (>30 updates/minute)
2. OperationRateLimiter blocks excessive registrations (>3/hour)
3. OperationRateLimiter blocks excessive verifications (>5/hour)
4. OperationRateLimiter blocks excessive withdrawals (>10/day or >3/hour)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, User as TelegramUser

from bot.middlewares.rate_limit_middleware import RateLimitMiddleware
from bot.utils.operation_rate_limit import OperationRateLimiter


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_rate_limit_middleware_blocks_spam() -> None:
    """
    Test that RateLimitMiddleware blocks spam (>30 updates/minute).

    Scenario:
    GIVEN: User sends messages
    WHEN: User sends >30 updates in 1 minute
    THEN: 31st and above are blocked, handler is NOT called
    """
    # GIVEN: Create mock Redis
    mock_redis = AsyncMock()
    
    # Simulate: first 30 requests pass, 31st is blocked
    call_count = 0
    
    async def mock_get(key):
        if "rate_limit" in key:
            return "30"  # At limit
        return None
    
    async def mock_incr(key):
        nonlocal call_count
        call_count += 1
        return call_count  # Returns 31 on 31st call
    
    mock_redis.get = AsyncMock(side_effect=mock_get)
    mock_redis.incr = AsyncMock(side_effect=mock_incr)
    mock_redis.expire = AsyncMock()
    
    # GIVEN: Create middleware
    middleware = RateLimitMiddleware(
        redis_client=mock_redis,
        user_limit=30,
        user_window=60,
    )
    
    # WHEN: User sends 31st message
    handler_called = False
    
    async def mock_handler(event, data):
        nonlocal handler_called
        handler_called = True
        return "ok"
    
    telegram_user = TelegramUser(
        id=123456789,
        is_bot=False,
        first_name="Spam",
        last_name="User",
    )
    message = Message(
        message_id=31,
        date=1234567890,
        chat=MagicMock(id=123456789),
        from_user=telegram_user,
        text="/start",
    )
    
    data = {
        "event_from_user": telegram_user,
        "redis_client": mock_redis,
    }
    
    # Execute middleware
    result = await middleware(mock_handler, message, data)
    
    # THEN: Handler should NOT be called
    assert handler_called is False, "Handler should not be called when rate limited"
    assert result is None, "Middleware should return None when rate limited"


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_registration_rate_limit() -> None:
    """
    Test that registration rate limit blocks excessive registrations.

    Scenario:
    GIVEN: User tries to register
    WHEN: User makes >3 registration attempts in 1 hour
    THEN: 4th attempt is blocked with clear error message
    """
    # GIVEN: Create mock Redis
    mock_redis = AsyncMock()
    
    # Simulate: 3 registrations already made
    mock_redis.get = AsyncMock(return_value="3")  # At limit
    mock_redis.setex = AsyncMock()
    
    limiter = OperationRateLimiter(redis_client=mock_redis)
    
    # WHEN: User tries 4th registration
    telegram_id = 111111111
    allowed, error = await limiter.check_registration_limit(telegram_id)
    
    # THEN: Should be blocked
    assert allowed is False, "Should be blocked at registration limit (3/hour)"
    assert error is not None, "Error message should be provided"
    assert (
        "превышен" in error.lower() or "лимит" in error.lower() or "час" in error.lower()
    ), f"Error should mention limit: {error}"


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_verification_rate_limit() -> None:
    """
    Test that verification rate limit blocks excessive verifications.

    Scenario:
    GIVEN: User tries to verify
    WHEN: User makes >5 verification attempts in 1 hour
    THEN: 6th attempt is blocked with clear error message
    """
    # GIVEN: Create mock Redis
    mock_redis = AsyncMock()
    
    # Simulate: 5 verifications already made
    mock_redis.get = AsyncMock(return_value="5")  # At limit
    mock_redis.setex = AsyncMock()
    
    limiter = OperationRateLimiter(redis_client=mock_redis)
    
    # WHEN: User tries 6th verification
    telegram_id = 222222222
    allowed, error = await limiter.check_verification_limit(telegram_id)
    
    # THEN: Should be blocked
    assert allowed is False, "Should be blocked at verification limit (5/hour)"
    assert error is not None, "Error message should be provided"
    assert (
        "превышен" in error.lower() or "лимит" in error.lower() or "час" in error.lower()
    ), f"Error should mention limit: {error}"


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_withdrawal_rate_limits() -> None:
    """
    Test that withdrawal rate limits block excessive withdrawals.

    Scenario:
    GIVEN: User tries to withdraw
    WHEN: User makes >10 withdrawals per day OR >3 per hour
    THEN: Excessive withdrawal is blocked with clear error message
    """
    # GIVEN: Create mock Redis
    mock_redis = AsyncMock()
    limiter = OperationRateLimiter(redis_client=mock_redis)
    
    telegram_id = 333333333
    
    # Test 1: Daily limit (10 per day)
    # WHEN: User makes 11th withdrawal in a day
    mock_redis.get = AsyncMock(return_value="10")  # At daily limit
    mock_redis.setex = AsyncMock()
    
    allowed, error = await limiter.check_withdrawal_limit(telegram_id)
    
    # THEN: Should be blocked by daily limit
    assert allowed is False, "Should be blocked at daily limit (10/day)"
    assert error is not None, "Error message should be provided"
    assert (
        "дневной" in error.lower() or "день" in error.lower() or "10" in error
    ), f"Error should mention daily limit: {error}"
    
    # Test 2: Hourly limit (3 per hour)
    # WHEN: User makes 4th withdrawal in an hour (but daily limit OK)
    mock_redis.get = AsyncMock(side_effect=["0", "3"])  # Daily OK, hourly at limit
    
    allowed, error = await limiter.check_withdrawal_limit(telegram_id)
    
    # THEN: Should be blocked by hourly limit
    assert allowed is False, "Should be blocked at hourly limit (3/hour)"
    assert error is not None, "Error message should be provided"
    assert (
        "часовой" in error.lower() or "час" in error.lower() or "3" in error
    ), f"Error should mention hourly limit: {error}"


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limits() -> None:
    """
    Test that rate limiters allow operations within limits.

    Scenario:
    GIVEN: User performs operations
    WHEN: Operations are within limits
    THEN: All operations are allowed
    """
    # GIVEN: Create mock Redis
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # No previous attempts
    mock_redis.setex = AsyncMock()
    
    limiter = OperationRateLimiter(redis_client=mock_redis)
    
    telegram_id = 444444444
    
    # WHEN: User performs operations within limits
    # THEN: All should be allowed
    
    # Registration: 1st attempt (limit: 3/hour)
    allowed, error = await limiter.check_registration_limit(telegram_id)
    assert allowed is True, "First registration should be allowed"
    
    # Verification: 1st attempt (limit: 5/hour)
    allowed, error = await limiter.check_verification_limit(telegram_id)
    assert allowed is True, "First verification should be allowed"
    
    # Withdrawal: 1st attempt (limit: 10/day, 3/hour)
    mock_redis.get = AsyncMock(return_value=None)  # No previous withdrawals
    allowed, error = await limiter.check_withdrawal_limit(telegram_id)
    assert allowed is True, "First withdrawal should be allowed"


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_rate_limiter_fail_open_on_redis_unavailable() -> None:
    """
    Test that rate limiters fail open when Redis is unavailable.

    Scenario:
    GIVEN: Redis is unavailable
    WHEN: User performs operations
    THEN: All operations are allowed (fail open strategy)
    """
    # GIVEN: Redis is None
    limiter = OperationRateLimiter(redis_client=None)
    
    telegram_id = 555555555
    
    # WHEN: User performs operations
    # THEN: All should be allowed (fail open)
    
    allowed, error = await limiter.check_registration_limit(telegram_id)
    assert allowed is True, "Should allow when Redis is None"
    
    allowed, error = await limiter.check_verification_limit(telegram_id)
    assert allowed is True, "Should allow when Redis is None"
    
    allowed, error = await limiter.check_withdrawal_limit(telegram_id)
    assert allowed is True, "Should allow when Redis is None"
    
    # GIVEN: Redis raises errors
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=Exception("Connection error"))
    mock_redis.setex = AsyncMock(side_effect=Exception("Connection error"))
    
    limiter = OperationRateLimiter(redis_client=mock_redis)
    
    # WHEN: User performs operations
    # THEN: All should still be allowed (fail open)
    
    allowed, error = await limiter.check_registration_limit(telegram_id)
    assert allowed is True, "Should allow on Redis error (fail open)"
    
    allowed, error = await limiter.check_verification_limit(telegram_id)
    assert allowed is True, "Should allow on Redis error (fail open)"
    
    allowed, error = await limiter.check_withdrawal_limit(telegram_id)
    assert allowed is True, "Should allow on Redis error (fail open)"


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_combined_ddos_scenario() -> None:
    """
    Test combined DDoS scenario: spam + operation limits.

    Scenario:
    GIVEN: Attacker tries multiple attack vectors
    WHEN: Attacker sends spam AND tries excessive operations
    THEN: All attacks are blocked by respective limiters
    """
    # GIVEN: Create mock Redis
    mock_redis = AsyncMock()
    
    # Setup for spam blocking
    spam_redis = AsyncMock()
    spam_redis.get = AsyncMock(return_value="30")  # At spam limit
    spam_redis.incr = AsyncMock(return_value=31)
    spam_redis.expire = AsyncMock()
    
    # Setup for operation limits
    op_redis = AsyncMock()
    op_redis.get = AsyncMock(return_value="10")  # At withdrawal limit
    op_redis.setex = AsyncMock()
    
    # WHEN: Attacker sends spam (31st message)
    spam_middleware = RateLimitMiddleware(
        redis_client=spam_redis,
        user_limit=30,
        user_window=60,
    )
    
    handler_called = False
    
    async def mock_handler(event, data):
        nonlocal handler_called
        handler_called = True
        return "ok"
    
    telegram_user = TelegramUser(
        id=666666666,
        is_bot=False,
        first_name="Attacker",
    )
    message = Message(
        message_id=31,
        date=1234567890,
        chat=MagicMock(id=666666666),
        from_user=telegram_user,
        text="/start",
    )
    
    data = {
        "event_from_user": telegram_user,
        "redis_client": spam_redis,
    }
    
    # THEN: Spam is blocked
    result = await spam_middleware(mock_handler, message, data)
    assert handler_called is False, "Spam should be blocked"
    assert result is None, "Spam middleware should return None"
    
    # WHEN: Attacker tries excessive withdrawal
    op_limiter = OperationRateLimiter(redis_client=op_redis)
    allowed, error = await op_limiter.check_withdrawal_limit(telegram_user.id)
    
    # THEN: Withdrawal is blocked
    assert allowed is False, "Excessive withdrawal should be blocked"
    assert error is not None, "Error message should be provided"

