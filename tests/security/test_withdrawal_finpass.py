"""
Tests for withdrawal financial password verification.

Tests that financial password verification works correctly and earnings_blocked
is automatically unblocked after successful withdrawal.
"""

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, User as TelegramUser
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.transaction import TransactionType
from app.repositories.user_repository import UserRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.user_service import UserService
from app.utils.encryption import hash_password
from bot.handlers.withdrawal import process_financial_password
from bot.states.withdrawal import WithdrawalStates


@pytest.fixture
def memory_storage():
    """Create memory storage for FSM."""
    return MemoryStorage()


@pytest.fixture
async def fsm_context(memory_storage):
    """Create FSM context."""
    return FSMContext(storage=memory_storage, key=None, bot_id=1, user_id=1)


@pytest.fixture
async def user_with_finpass(db_session: AsyncSession) -> User:
    """Create user with financial password and balance."""
    user_repo = UserRepository(db_session)
    
    # Create hashed financial password using project's hash_password utility
    password = "test_finpass_123"
    password_hash = hash_password(password)
    
    user = await user_repo.create(
        telegram_id=123456789,
        wallet_address="0x1234567890123456789012345678901234567890",
        financial_password_hash=password_hash,
        balance=Decimal("100.0"),
        available_balance=Decimal("100.0"),
    )
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.security
@pytest.mark.asyncio
async def test_invalid_password_no_withdrawal_created(
    db_session: AsyncSession,
    user_with_finpass: User,
    fsm_context: FSMContext,
) -> None:
    """
    Test that invalid password prevents withdrawal creation.
    
    Scenario:
    1. User has balance and financial password
    2. User enters wrong password
    3. Verify: no withdrawal transaction created, earnings_blocked unchanged
    """
    # Set up FSM state
    await fsm_context.set_state(WithdrawalStates.waiting_for_financial_password)
    await fsm_context.update_data(amount=Decimal("50.0"))
    
    # Get initial earnings_blocked state
    initial_earnings_blocked = user_with_finpass.earnings_blocked
    
    # Create message with wrong password
    message = Message(
        from_user=TelegramUser(
            id=user_with_finpass.telegram_id,
            is_bot=False,
            first_name="Test",
        ),
        text="wrong_password",
        message_id=1,
        date=None,
        chat=None,
    )
    
    # Prepare data
    data = {
        "session": db_session,
        "user": user_with_finpass,
        "is_admin": False,
    }
    
    # Call handler
    await process_financial_password(message, fsm_context, **data)
    
    # Verify: no withdrawal transaction created
    transaction_repo = TransactionRepository(db_session)
    withdrawals = await transaction_repo.get_by_user(
        user_with_finpass.id,
        type=TransactionType.WITHDRAWAL.value,
    )
    assert len(withdrawals) == 0, "No withdrawal should be created with wrong password"
    
    # Verify: earnings_blocked unchanged
    await db_session.refresh(user_with_finpass)
    assert (
        user_with_finpass.earnings_blocked == initial_earnings_blocked
    ), "earnings_blocked should not change with wrong password"


@pytest.mark.security
@pytest.mark.asyncio
async def test_valid_password_normal_withdrawal(
    db_session: AsyncSession,
    user_with_finpass: User,
    fsm_context: FSMContext,
) -> None:
    """
    Test that valid password allows withdrawal when earnings_blocked=False.
    
    Scenario:
    1. User has balance, earnings_blocked=False
    2. User enters correct password
    3. Verify: withdrawal created, earnings_blocked remains False
    """
    # Ensure earnings_blocked is False
    user_service = UserService(db_session)
    await user_service.block_earnings(user_with_finpass.id, block=False)
    await db_session.commit()
    await db_session.refresh(user_with_finpass)
    assert user_with_finpass.earnings_blocked is False
    
    # Set up FSM state
    await fsm_context.set_state(WithdrawalStates.waiting_for_financial_password)
    await fsm_context.update_data(amount=Decimal("50.0"))
    
    # Create message with correct password
    message = Message(
        from_user=TelegramUser(
            id=user_with_finpass.telegram_id,
            is_bot=False,
            first_name="Test",
        ),
        text="test_finpass_123",
        message_id=1,
        date=None,
        chat=None,
    )
    
    # Prepare data
    data = {
        "session": db_session,
        "user": user_with_finpass,
        "is_admin": False,
    }
    
    # Call handler
    await process_financial_password(message, fsm_context, **data)
    
    # Verify: withdrawal transaction created
    transaction_repo = TransactionRepository(db_session)
    withdrawals = await transaction_repo.get_by_user(
        user_with_finpass.id,
        type=TransactionType.WITHDRAWAL.value,
    )
    assert len(withdrawals) > 0, "Withdrawal should be created with correct password"
    
    # Verify: earnings_blocked remains False
    await db_session.refresh(user_with_finpass)
    assert (
        user_with_finpass.earnings_blocked is False
    ), "earnings_blocked should remain False when already unblocked"


@pytest.mark.security
@pytest.mark.asyncio
async def test_valid_password_unblocks_earnings(
    db_session: AsyncSession,
    user_with_finpass: User,
    fsm_context: FSMContext,
) -> None:
    """
    Test that valid password unblocks earnings_blocked after successful withdrawal.
    
    Scenario:
    1. User has balance, earnings_blocked=True (from finpass recovery)
    2. User enters correct password
    3. Verify: withdrawal created, earnings_blocked becomes False
    """
    # Set earnings_blocked to True (simulating finpass recovery scenario)
    user_service = UserService(db_session)
    await user_service.block_earnings(user_with_finpass.id, block=True)
    await db_session.commit()
    await db_session.refresh(user_with_finpass)
    assert user_with_finpass.earnings_blocked is True
    
    # Set up FSM state
    await fsm_context.set_state(WithdrawalStates.waiting_for_financial_password)
    await fsm_context.update_data(amount=Decimal("50.0"))
    
    # Create message with correct password
    message = Message(
        from_user=TelegramUser(
            id=user_with_finpass.telegram_id,
            is_bot=False,
            first_name="Test",
        ),
        text="test_finpass_123",
        message_id=1,
        date=None,
        chat=None,
    )
    
    # Prepare data
    data = {
        "session": db_session,
        "user": user_with_finpass,
        "is_admin": False,
    }
    
    # Call handler
    await process_financial_password(message, fsm_context, **data)
    
    # Verify: withdrawal transaction created
    transaction_repo = TransactionRepository(db_session)
    withdrawals = await transaction_repo.get_by_user(
        user_with_finpass.id,
        type=TransactionType.WITHDRAWAL.value,
    )
    assert len(withdrawals) > 0, "Withdrawal should be created with correct password"
    
    # Verify: earnings_blocked is now False
    await db_session.refresh(user_with_finpass)
    assert (
        user_with_finpass.earnings_blocked is False
    ), "earnings_blocked should be unblocked after successful finpass usage"

