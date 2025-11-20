"""
Tests for admin login rate limiting.

Tests that too many failed login attempts result in automatic blocking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blacklist import BlacklistActionType
from app.repositories.blacklist_repository import BlacklistRepository
from app.repositories.user_repository import UserRepository
from app.services.admin_service import AdminService, ADMIN_LOGIN_MAX_ATTEMPTS


@pytest.mark.security
@pytest.mark.asyncio
async def test_failed_login_attempts_tracked(
    db_session: AsyncSession,
) -> None:
    """
    Test that failed login attempts are tracked in Redis.

    Scenario:
    1. Create admin
    2. Make failed login attempts
    3. Verify Redis key is incremented
    """
    # Create admin
    admin_service = AdminService(db_session)
    admin, master_key, _ = await admin_service.create_admin(
        telegram_id=555555555,
        role="admin",
        created_by=1,
    )
    await db_session.commit()

    # Create mock Redis client
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.setex = AsyncMock()

    admin_service.redis_client = mock_redis

    # Make failed login attempt
    await admin_service.login(
        telegram_id=admin.telegram_id,
        master_key="wrong_key",
    )

    # Verify Redis was called
    assert mock_redis.get.called, "Redis get should be called"
    assert mock_redis.setex.called, "Redis setex should be called"


@pytest.mark.security
@pytest.mark.asyncio
async def test_exceeding_limit_blocks_telegram_id(
    db_session: AsyncSession,
) -> None:
    """
    Test that exceeding login limit automatically blocks Telegram ID.

    Scenario:
    1. Create admin
    2. Simulate ADMIN_LOGIN_MAX_ATTEMPTS failed logins
    3. Verify blacklist entry is created with BLOCKED action
    """
    # Create admin
    admin_service = AdminService(db_session)
    admin, _, _ = await admin_service.create_admin(
        telegram_id=666666666,
        role="admin",
        created_by=1,
    )
    await db_session.commit()

    # Create user with same telegram_id
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=admin.telegram_id,
        wallet_address="0x6666666666666666666666666666666666666666",
        financial_password_hash="test_hash",
    )
    await db_session.commit()

    # Create mock Redis that returns count >= limit
    mock_redis = AsyncMock()
    mock_redis.get.return_value = str(ADMIN_LOGIN_MAX_ATTEMPTS)
    mock_redis.setex = AsyncMock()

    admin_service.redis_client = mock_redis

    # Track failed login (should trigger blocking)
    await admin_service._track_failed_login(admin.telegram_id)

    # Verify blacklist entry was created
    blacklist_repo = BlacklistRepository(db_session)
    blacklist_entry = await blacklist_repo.get_by_telegram_id(admin.telegram_id)

    assert blacklist_entry is not None
    assert blacklist_entry.action_type == BlacklistActionType.BLOCKED
    assert blacklist_entry.is_active is True
    assert "failed admin login attempts" in blacklist_entry.reason.lower()

    # Verify user is banned
    user_after = await user_repo.get_by_telegram_id(admin.telegram_id)
    assert user_after is not None
    assert user_after.is_banned is True


@pytest.mark.security
@pytest.mark.asyncio
async def test_successful_login_clears_attempts(
    db_session: AsyncSession,
) -> None:
    """
    Test that successful login clears failed attempt counter.

    Scenario:
    1. Create admin
    2. Make failed login attempts (tracked in Redis)
    3. Make successful login
    4. Verify Redis key is deleted
    """
    # Create admin
    admin_service = AdminService(db_session)
    admin, master_key, _ = await admin_service.create_admin(
        telegram_id=777777777,
        role="admin",
        created_by=1,
    )
    await db_session.commit()

    # Create mock Redis
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "3"  # 3 failed attempts
    mock_redis.setex = AsyncMock()
    mock_redis.delete = AsyncMock()

    admin_service.redis_client = mock_redis

    # Successful login
    await admin_service.login(
        telegram_id=admin.telegram_id,
        master_key=master_key,
    )

    # Verify delete was called to clear attempts
    assert mock_redis.delete.called, "Redis delete should be called on successful login"
    # Verify the correct key was deleted
    call_args = mock_redis.delete.call_args[0][0]
    assert "admin_login_attempts" in call_args
    assert str(admin.telegram_id) in call_args

