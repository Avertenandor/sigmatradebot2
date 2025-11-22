"""
Unit tests for DepositValidationService.

Tests deposit level validation, order checking, and partner requirements.
"""

import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.deposit_validation_service import (
    DepositValidationService,
    DEPOSIT_LEVELS,
    PARTNER_REQUIREMENTS,
)


@pytest.mark.asyncio
async def test_can_purchase_level_1_without_partners(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    test_user,  # pylint: disable=redefined-outer-name
):
    """Test that level 1 can be purchased without partners."""
    service = DepositValidationService(db_session)
    can_purchase, error = await service.can_purchase_level(
        user_id=test_user.id, level=1
    )
    assert can_purchase is True
    assert error is None


@pytest.mark.asyncio
async def test_cannot_skip_levels(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    test_user,  # pylint: disable=redefined-outer-name
):
    """Test that levels must be purchased in strict order."""
    service = DepositValidationService(db_session)
    # Try to purchase level 3 without having level 2
    can_purchase, error = await service.can_purchase_level(
        user_id=test_user.id, level=3
    )
    assert can_purchase is False
    assert error is not None
    assert "уровень 2" in error or "уровень 3" in error


@pytest.mark.asyncio
async def test_invalid_level_rejected(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    test_user,  # pylint: disable=redefined-outer-name
):
    """Test that invalid levels are rejected."""
    service = DepositValidationService(db_session)
    can_purchase, error = await service.can_purchase_level(
        user_id=test_user.id, level=99
    )
    assert can_purchase is False
    assert "Неверный уровень" in error


@pytest.mark.asyncio
async def test_get_available_levels(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    test_user,  # pylint: disable=redefined-outer-name
):
    """Test getting available levels for user."""
    service = DepositValidationService(db_session)
    levels_status = await service.get_available_levels(user_id=test_user.id)

    assert isinstance(levels_status, dict)
    assert len(levels_status) == 5  # 5 deposit levels

    # Level 1 should be available for new user
    assert levels_status[1]["status"] == "available"
    assert levels_status[1]["amount"] == DEPOSIT_LEVELS[1]

    # Levels 2-5 should be unavailable (no previous levels, no partners)
    for level in [2, 3, 4, 5]:
        assert levels_status[level]["status"] == "unavailable"
        assert levels_status[level]["error"] is not None

