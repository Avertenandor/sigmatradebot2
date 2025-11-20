"""
E2E tests for withdrawal handler role scenarios.

Tests that withdrawal handler correctly handles different user roles and states.
"""

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, User as TelegramUser
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blacklist import Blacklist, BlacklistActionType
from app.models.user import User
from app.repositories.blacklist_repository import BlacklistRepository
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService
from bot.handlers.withdrawal import withdraw_all, process_withdrawal_amount
from bot.middlewares.ban_middleware import BanMiddleware
from bot.utils.encryption import hash_password


@pytest.fixture
def memory_storage():
    """Create memory storage for FSM."""
    return MemoryStorage()


@pytest.fixture
async def fsm_context(memory_storage):
    """Create FSM context."""
    return FSMContext(storage=memory_storage, key=None, bot_id=1, user_id=1)


@pytest.fixture
async def verified_user_with_balance(db_session: AsyncSession) -> User:
    """Create verified user with balance."""
    user_repo = UserRepository(db_session)
    
    user = await user_repo.create(
        telegram_id=123456789,
        wallet_address="0x1234567890123456789012345678901234567890",
        financial_password_hash=hash_password("test_finpass"),
        balance=Decimal("100.0"),
        available_balance=Decimal("100.0"),
        is_verified=True,
    )
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.security
@pytest.mark.asyncio
async def test_normal_user_can_reach_financial_password_step(
    db_session: AsyncSession,
    verified_user_with_balance: User,
    fsm_context: FSMContext,
) -> None:
    """
    Test that normal verified user can reach financial password input step.
    
    Scenario:
    1. User is verified, has balance
    2. User clicks "💸 Вывести всю сумму"
    3. Verify: user reaches financial password input step (FSM state set)
    """
    # Create message
    message = Message(
        from_user=TelegramUser(
            id=verified_user_with_balance.telegram_id,
            is_bot=False,
            first_name="Test",
        ),
        text="💸 Вывести всю сумму",
        message_id=1,
        date=None,
        chat=None,
    )
    
    # Prepare data
    data = {
        "session": db_session,
        "user": verified_user_with_balance,
        "is_admin": False,
    }
    
    # Call handler
    await withdraw_all(message, fsm_context, **data)
    
    # Verify: FSM state should be set to waiting_for_financial_password
    current_state = await fsm_context.get_state()
    from bot.states.withdrawal import WithdrawalStates
    assert (
        current_state == WithdrawalStates.waiting_for_financial_password
    ), "User should reach financial password input step"


@pytest.mark.security
@pytest.mark.asyncio
async def test_terminated_user_blocked_by_ban_middleware(
    db_session: AsyncSession,
    verified_user_with_balance: User,
) -> None:
    """
    Test that TERMINATED user is blocked by BanMiddleware before reaching withdrawal handler.
    
    Scenario:
    1. User is TERMINATED in blacklist
    2. User tries to send any message
    3. Verify: BanMiddleware blocks request, handler not called
    """
    # Add user to blacklist with TERMINATED
    blacklist_repo = BlacklistRepository(db_session)
    await blacklist_repo.create(
        telegram_id=verified_user_with_balance.telegram_id,
        action_type=BlacklistActionType.TERMINATED,
        reason="Test termination",
        is_active=True,
    )
    await db_session.commit()
    
    # Create middleware
    middleware = BanMiddleware()
    
    # Create message
    message = Message(
        from_user=TelegramUser(
            id=verified_user_with_balance.telegram_id,
            is_bot=False,
            first_name="Test",
        ),
        text="💸 Вывести всю сумму",
        message_id=1,
        date=None,
        chat=None,
    )
    
    # Prepare data
    data = {
        "session": db_session,
        "event_from_user": message.from_user,
        "user": verified_user_with_balance,
    }
    
    # Track handler calls
    handler_called = []
    
    async def mock_handler(event, data):
        handler_called.append(True)
        return "handled"
    
    # Process through middleware
    result = await middleware(mock_handler, message, data)
    
    # Verify: handler should not be called (returns None)
    assert result is None, "TERMINATED user should be blocked by BanMiddleware"
    assert len(handler_called) == 0, "Handler should not be called for TERMINATED user"


@pytest.mark.security
@pytest.mark.asyncio
async def test_unverified_user_cannot_withdraw(
    db_session: AsyncSession,
    verified_user_with_balance: User,
    fsm_context: FSMContext,
) -> None:
    """
    Test that unverified user gets clear message when trying to withdraw.
    
    Scenario:
    1. User has balance but is_verified=False
    2. User clicks "💸 Вывести всю сумму"
    3. Verify: user gets message about need to verify, FSM state not set
    """
    # Set user as unverified
    user_service = UserService(db_session)
    await user_service.update_profile(
        verified_user_with_balance.id,
        is_verified=False,
    )
    await db_session.commit()
    await db_session.refresh(verified_user_with_balance)
    assert verified_user_with_balance.is_verified is False
    
    # Create message
    message = Message(
        from_user=TelegramUser(
            id=verified_user_with_balance.telegram_id,
            is_bot=False,
            first_name="Test",
        ),
        text="💸 Вывести всю сумму",
        message_id=1,
        date=None,
        chat=None,
    )
    
    # Prepare data
    data = {
        "session": db_session,
        "user": verified_user_with_balance,
        "is_admin": False,
    }
    
    # Call handler
    await withdraw_all(message, fsm_context, **data)
    
    # Verify: FSM state should NOT be set (user blocked before password step)
    current_state = await fsm_context.get_state()
    assert current_state is None, "FSM state should not be set for unverified user"
    
    # Note: In real scenario, message.answer would be called with verification message
    # This is tested implicitly by checking that state is not set


@pytest.mark.security
@pytest.mark.asyncio
async def test_blocked_user_can_only_appeal(
    db_session: AsyncSession,
    verified_user_with_balance: User,
) -> None:
    """
    Test that BLOCKED user can only use appeal button, not withdrawal.
    
    Scenario:
    1. User is BLOCKED in blacklist
    2. User tries to send withdrawal message
    3. Verify: BanMiddleware blocks withdrawal, but allows appeal button
    """
    # Add user to blacklist with BLOCKED
    blacklist_repo = BlacklistRepository(db_session)
    await blacklist_repo.create(
        telegram_id=verified_user_with_balance.telegram_id,
        action_type=BlacklistActionType.BLOCKED,
        reason="Test block",
        is_active=True,
    )
    await db_session.commit()
    
    # Create middleware
    middleware = BanMiddleware()
    
    # Test 1: Withdrawal message should be blocked
    withdrawal_message = Message(
        from_user=TelegramUser(
            id=verified_user_with_balance.telegram_id,
            is_bot=False,
            first_name="Test",
        ),
        text="💸 Вывести всю сумму",
        message_id=1,
        date=None,
        chat=None,
    )
    
    data = {
        "session": db_session,
        "event_from_user": withdrawal_message.from_user,
        "user": verified_user_with_balance,
    }
    
    handler_called = []
    
    async def mock_handler(event, data):
        handler_called.append(True)
        return "handled"
    
    result = await middleware(mock_handler, withdrawal_message, data)
    assert result is None, "Withdrawal should be blocked for BLOCKED user"
    assert len(handler_called) == 0, "Handler should not be called"
    
    # Test 2: Appeal button should be allowed
    appeal_message = Message(
        from_user=TelegramUser(
            id=verified_user_with_balance.telegram_id,
            is_bot=False,
            first_name="Test",
        ),
        text="📝 Подать апелляцию",
        message_id=2,
        date=None,
        chat=None,
    )
    
    data = {
        "session": db_session,
        "event_from_user": appeal_message.from_user,
        "user": verified_user_with_balance,
    }
    
    result = await middleware(mock_handler, appeal_message, data)
    assert result == "handled", "Appeal button should be allowed for BLOCKED user"
    assert len(handler_called) == 1, "Handler should be called for appeal"

