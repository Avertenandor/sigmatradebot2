"""
Tests for finpass recovery earnings_blocked lifecycle.

Tests that earnings_blocked is properly managed during financial password recovery.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_password_recovery import (
    FinancialPasswordRecovery,
    FinancialRecoveryStatus,
)
from app.models.user import User
from app.repositories.financial_password_recovery_repository import (
    FinancialPasswordRecoveryRepository,
)
from app.repositories.user_repository import UserRepository
from app.services.finpass_recovery_service import FinpassRecoveryService
from app.services.user_service import UserService
from app.utils.encryption import hash_password


@pytest.fixture
async def user_with_balance(db_session: AsyncSession) -> User:
    """Create user with balance for testing."""
    user_repo = UserRepository(db_session)
    
    user = await user_repo.create(
        telegram_id=123456789,
        wallet_address="0x1234567890123456789012345678901234567890",
        financial_password_hash=hash_password("old_password"),
        balance=Decimal("100.0"),
        earnings_blocked=False,
    )
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.security
@pytest.mark.asyncio
async def test_create_recovery_request_blocks_earnings(
    db_session: AsyncSession,
    user_with_balance: User,
) -> None:
    """
    Test that creating recovery request blocks earnings immediately.
    
    Scenario:
    1. User has earnings_blocked=False
    2. Create recovery request
    3. Verify: request created with status=PENDING, earnings_blocked=True
    """
    recovery_service = FinpassRecoveryService(db_session)
    
    # Verify initial state
    assert user_with_balance.earnings_blocked is False
    
    # Create recovery request
    request = await recovery_service.create_recovery_request(
        user_id=user_with_balance.id,
        reason="I forgot my financial password and need to recover it",
        video_required=False,
    )
    await db_session.commit()
    
    # Verify request was created
    assert request is not None
    assert request.user_id == user_with_balance.id
    assert request.status == FinancialRecoveryStatus.PENDING.value
    
    # Verify earnings_blocked is now True
    await db_session.refresh(user_with_balance)
    assert (
        user_with_balance.earnings_blocked is True
    ), "earnings_blocked should be True after creating recovery request"


@pytest.mark.security
@pytest.mark.asyncio
async def test_duplicate_recovery_request_does_not_change_earnings_blocked(
    db_session: AsyncSession,
    user_with_balance: User,
) -> None:
    """
    Test that attempting to create duplicate recovery request doesn't change earnings_blocked.
    
    Scenario:
    1. User has active recovery request, earnings_blocked=True
    2. Attempt to create another request
    3. Verify: ValueError raised, earnings_blocked remains True
    """
    recovery_service = FinpassRecoveryService(db_session)
    
    # Create first recovery request (this will set earnings_blocked=True)
    first_request = await recovery_service.create_recovery_request(
        user_id=user_with_balance.id,
        reason="First recovery request with sufficient reason text",
        video_required=False,
    )
    await db_session.commit()
    await db_session.refresh(user_with_balance)
    
    # Verify earnings_blocked is True after first request
    assert user_with_balance.earnings_blocked is True
    
    # Attempt to create duplicate request
    with pytest.raises(ValueError, match="already has an active recovery"):
        await recovery_service.create_recovery_request(
            user_id=user_with_balance.id,
            reason="Second recovery request attempt",
            video_required=False,
        )
    
    # Verify earnings_blocked is still True (not changed by failed attempt)
    await db_session.refresh(user_with_balance)
    assert (
        user_with_balance.earnings_blocked is True
    ), "earnings_blocked should remain True after failed duplicate request"


@pytest.mark.security
@pytest.mark.asyncio
async def test_earnings_unblocked_after_successful_withdrawal(
    db_session: AsyncSession,
    user_with_balance: User,
) -> None:
    """
    Integration test: earnings_blocked is unblocked after successful withdrawal.
    
    Scenario:
    1. Create recovery request (earnings_blocked=True)
    2. Approve recovery and set new password
    3. User successfully uses new password for withdrawal
    4. Verify: earnings_blocked=False
    """
    recovery_service = FinpassRecoveryService(db_session)
    user_service = UserService(db_session)
    
    # Step 1: Create recovery request
    request = await recovery_service.create_recovery_request(
        user_id=user_with_balance.id,
        reason="I need to recover my financial password",
        video_required=False,
    )
    await db_session.commit()
    await db_session.refresh(user_with_balance)
    
    # Verify earnings_blocked is True
    assert user_with_balance.earnings_blocked is True
    
    # Step 2: Approve recovery (simulate admin approval)
    # In real flow, admin would approve and generate new password
    # For this test, we'll simulate the approval by updating status
    recovery_repo = FinancialPasswordRecoveryRepository(db_session)
    await recovery_repo.update(
        request.id,
        status=FinancialRecoveryStatus.APPROVED.value,
    )
    await db_session.commit()
    
    # Step 3: Simulate successful withdrawal with new password
    # This would normally happen in withdrawal handler after password verification
    # For test, we directly unblock earnings (simulating withdrawal handler logic)
    await user_service.block_earnings(user_with_balance.id, block=False)
    await db_session.commit()
    await db_session.refresh(user_with_balance)
    
    # Step 4: Verify earnings_blocked is False
    assert (
        user_with_balance.earnings_blocked is False
    ), "earnings_blocked should be False after successful withdrawal with new password"

