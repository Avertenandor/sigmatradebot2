"""
Unit tests for WithdrawalService.

Tests withdrawal request validation, balance checking, and processing.
"""

import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.withdrawal_service import WithdrawalService, MIN_WITHDRAWAL_AMOUNT


def test_minimum_withdrawal_amount():
    """Test that minimum withdrawal amount is configured."""
    assert MIN_WITHDRAWAL_AMOUNT == Decimal("5.0")
    assert (
        WithdrawalService.get_min_withdrawal_amount() == Decimal("5.0")
    )


@pytest.mark.asyncio
async def test_withdrawal_below_minimum_rejected(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    test_user,  # pylint: disable=redefined-outer-name
):
    """Test that withdrawals below minimum are rejected."""
    service = WithdrawalService(db_session)
    transaction, error = await service.request_withdrawal(
        user_id=test_user.id,
        amount=Decimal("1.0"),  # Below minimum
        available_balance=Decimal("10.0"),
    )
    assert transaction is None
    assert error is not None
    assert "Минимальная сумма" in error or "minimum" in error.lower()


@pytest.mark.asyncio
async def test_withdrawal_insufficient_balance_rejected(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    test_user,  # pylint: disable=redefined-outer-name
):
    """Test that withdrawals exceeding balance are rejected."""
    service = WithdrawalService(db_session)
    transaction, error = await service.request_withdrawal(
        user_id=test_user.id,
        amount=Decimal("100.0"),
        available_balance=Decimal("10.0"),  # Insufficient
    )
    assert transaction is None
    assert error is not None
    assert "Недостаточно" in error or "insufficient" in error.lower()

