"""
Tests for BanMiddleware security functionality.

Tests that blocked and terminated users are properly restricted.
"""

import pytest
from aiogram.types import Message, User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blacklist import Blacklist, BlacklistActionType
from app.repositories.blacklist_repository import BlacklistRepository
from app.repositories.user_repository import UserRepository
from bot.middlewares.ban_middleware import BanMiddleware


@pytest.mark.security
@pytest.mark.asyncio
async def test_terminated_user_blocked_completely(
    db_session: AsyncSession,
) -> None:
    """
    Test that TERMINATED users cannot interact with bot at all.

    Scenario:
    1. Create user and add to blacklist with TERMINATED action
    2. Try to send message
    3. Verify that handler is not called (returns None)
    """
    # Create test user
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=123456789,
        wallet_address="0x1234567890123456789012345678901234567890",
        financial_password_hash="test_hash",
    )
    await db_session.commit()

    # Add to blacklist with TERMINATED
    blacklist_repo = BlacklistRepository(db_session)
    blacklist_entry = await blacklist_repo.create(
        telegram_id=user.telegram_id,
        action_type=BlacklistActionType.TERMINATED,
        reason="Test termination",
        is_active=True,
    )
    await db_session.commit()

    # Create middleware
    middleware = BanMiddleware()

    # Create mock handler that should not be called
    handler_called = False

    async def mock_handler(event, data):
        nonlocal handler_called
        handler_called = True
        return "handler_result"

    # Create mock message event
    telegram_user = TelegramUser(
        id=user.telegram_id,
        is_bot=False,
        first_name="Test",
    )
    message = Message(
        message_id=1,
        date=None,
        chat=None,
        from_user=telegram_user,
        text="/start",
    )

    # Prepare data
    data = {
        "event_from_user": telegram_user,
        "session": db_session,
    }

    # Call middleware
    result = await middleware(mock_handler, message, data)

    # Verify handler was not called
    assert not handler_called, "Handler should not be called for TERMINATED user"
    assert result is None, "Middleware should return None for TERMINATED user"


@pytest.mark.security
@pytest.mark.asyncio
async def test_blocked_user_only_appeal_allowed(
    db_session: AsyncSession,
) -> None:
    """
    Test that BLOCKED users can only use /start and appeal button.

    Scenarios:
    1. BLOCKED user can use /start
    2. BLOCKED user can click appeal button
    3. BLOCKED user cannot use other commands
    """
    # Create test user
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=987654321,
        wallet_address="0x9876543210987654321098765432109876543210",
        financial_password_hash="test_hash",
    )
    await db_session.commit()

    # Add to blacklist with BLOCKED
    blacklist_repo = BlacklistRepository(db_session)
    blacklist_entry = await blacklist_repo.create(
        telegram_id=user.telegram_id,
        action_type=BlacklistActionType.BLOCKED,
        reason="Test block",
        is_active=True,
    )
    await db_session.commit()

    middleware = BanMiddleware()
    handler_called = False

    async def mock_handler(event, data):
        nonlocal handler_called
        handler_called = True
        return "handler_result"

    telegram_user = TelegramUser(
        id=user.telegram_id,
        is_bot=False,
        first_name="Test",
    )

    # Test 1: /start should be allowed
    message_start = Message(
        message_id=1,
        date=None,
        chat=None,
        from_user=telegram_user,
        text="/start",
    )
    data = {
        "event_from_user": telegram_user,
        "session": db_session,
    }

    result = await middleware(mock_handler, message_start, data)
    assert handler_called, "/start should be allowed for BLOCKED user"
    assert result == "handler_result"
    handler_called = False

    # Test 2: Appeal button should be allowed
    message_appeal = Message(
        message_id=2,
        date=None,
        chat=None,
        from_user=telegram_user,
        text="📝 Подать апелляцию",
    )

    result = await middleware(mock_handler, message_appeal, data)
    assert handler_called, "Appeal button should be allowed for BLOCKED user"
    assert result == "handler_result"
    handler_called = False

    # Test 3: Other commands should be blocked
    message_other = Message(
        message_id=3,
        date=None,
        chat=None,
        from_user=telegram_user,
        text="💰 Депозит",
    )

    result = await middleware(mock_handler, message_other, data)
    assert not handler_called, "Other commands should be blocked"
    assert result is None, "Middleware should return None for blocked commands"


@pytest.mark.security
@pytest.mark.asyncio
async def test_blacklist_entry_passed_to_data(
    db_session: AsyncSession,
) -> None:
    """
    Test that blacklist_entry is passed to handler data.

    Verify that middleware sets data["blacklist_entry"] for handlers.
    """
    # Create test user
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=111222333,
        wallet_address="0x1112223334445556667778889990001112223334",
        financial_password_hash="test_hash",
    )
    await db_session.commit()

    # Add to blacklist
    blacklist_repo = BlacklistRepository(db_session)
    blacklist_entry = await blacklist_repo.create(
        telegram_id=user.telegram_id,
        action_type=BlacklistActionType.BLOCKED,
        reason="Test",
        is_active=True,
    )
    await db_session.commit()

    middleware = BanMiddleware()
    received_blacklist_entry = None

    async def mock_handler(event, data):
        nonlocal received_blacklist_entry
        received_blacklist_entry = data.get("blacklist_entry")
        return "handler_result"

    telegram_user = TelegramUser(
        id=user.telegram_id,
        is_bot=False,
        first_name="Test",
    )
    message = Message(
        message_id=1,
        date=None,
        chat=None,
        from_user=telegram_user,
        text="/start",
    )
    data = {
        "event_from_user": telegram_user,
        "session": db_session,
    }

    await middleware(mock_handler, message, data)

    # Verify blacklist_entry is in data
    assert received_blacklist_entry is not None
    assert received_blacklist_entry.id == blacklist_entry.id
    assert received_blacklist_entry.action_type == BlacklistActionType.BLOCKED

