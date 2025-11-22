"""
Unit tests for ReferralService.

Tests referral chain creation, reward processing, and statistics.
"""

import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.referral_service import ReferralService, REFERRAL_RATES


@pytest.mark.asyncio
async def test_create_referral_relationships(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    create_user_helper,  # pylint: disable=redefined-outer-name
):
    """Test creating referral relationships."""
    service = ReferralService(db_session)

    # Create test users
    referrer = await create_user_helper(telegram_id=600000001)
    referred = await create_user_helper(telegram_id=600000002)

    success, error = await service.create_referral_relationships(
        new_user_id=referred.id,
        direct_referrer_id=referrer.id,
    )

    assert success is True
    assert error is None


@pytest.mark.asyncio
async def test_self_referral_prevented(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    test_user,  # pylint: disable=redefined-outer-name
):
    """Test that self-referral is prevented."""
    service = ReferralService(db_session)
    success, error = await service.create_referral_relationships(
        new_user_id=test_user.id,
        direct_referrer_id=test_user.id,
    )
    assert success is False
    assert error is not None
    assert "самого себя" in error or "self" in error.lower()


@pytest.mark.asyncio
async def test_referral_rates_configured():
    """Test that referral rates are properly configured."""
    assert REFERRAL_RATES[1] == Decimal("0.03")  # 3%
    assert REFERRAL_RATES[2] == Decimal("0.02")  # 2%
    assert REFERRAL_RATES[3] == Decimal("0.05")  # 5%


@pytest.mark.asyncio
async def test_get_referral_stats(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    test_user,  # pylint: disable=redefined-outer-name
):
    """Test getting referral statistics."""
    service = ReferralService(db_session)
    stats = await service.get_referral_stats(user_id=test_user.id)

    assert isinstance(stats, dict)
    assert "direct_referrals" in stats
    assert "level2_referrals" in stats
    assert "level3_referrals" in stats
    assert "total_earned" in stats
    assert "pending_earnings" in stats
    assert "paid_earnings" in stats

