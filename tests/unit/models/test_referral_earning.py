"""
Unit tests for ReferralEarning model.

Tests referral earnings tracking and payment status.
"""

import pytest
from decimal import Decimal

from app.models.referral import Referral
from app.models.referral_earning import ReferralEarning


class TestReferralEarningModel:
    """Tests for ReferralEarning model."""

    @pytest.mark.asyncio
    async def test_create_referral_earning(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_referral_chain,  # pylint: disable=redefined-outer-name
    ):
        """Test creating referral earning."""
        referrer, level1, _, _ = test_referral_chain

        # First create Referral relationship
        referral = Referral(
            referrer_id=referrer.id,
            referral_id=level1.id,
            level=1,
        )
        db_session.add(referral)
        await db_session.commit()
        await db_session.refresh(referral)

        # Act - create earning linked to referral
        earning = ReferralEarning(
            referral_id=referral.id,  # Links to Referral, not User
            amount=Decimal("3.00"),  # 3% of 100
            paid=False,
        )
        db_session.add(earning)
        await db_session.commit()
        await db_session.refresh(earning)

        # Assert
        assert earning.id is not None
        assert earning.referral_id == referral.id
        assert earning.amount == Decimal("3.00")
        assert earning.paid is False

    @pytest.mark.asyncio
    async def test_referral_earning_payment_status(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_referral_chain,  # pylint: disable=redefined-outer-name
    ):
        """Test updating referral earning payment status."""
        referrer, level1, _, _ = test_referral_chain

        # First create Referral relationship
        referral = Referral(
            referrer_id=referrer.id,
            referral_id=level1.id,
            level=1,
        )
        db_session.add(referral)
        await db_session.commit()
        await db_session.refresh(referral)

        # Create earning
        earning = ReferralEarning(
            referral_id=referral.id,
            amount=Decimal("3.00"),
            paid=False,
        )
        db_session.add(earning)
        await db_session.commit()

        # Update to paid
        earning.paid = True
        earning.tx_hash = "0x" + "a" * 64
        await db_session.commit()
        await db_session.refresh(earning)

        # Assert
        assert earning.paid is True
        assert earning.tx_hash is not None

    @pytest.mark.asyncio
    async def test_referral_earning_properties(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_referral_chain,  # pylint: disable=redefined-outer-name
    ):
        """Test ReferralEarning properties."""
        referrer, level1, _, _ = test_referral_chain

        # First create Referral relationship
        referral = Referral(
            referrer_id=referrer.id,
            referral_id=level1.id,
            level=1,
        )
        db_session.add(referral)
        await db_session.commit()
        await db_session.refresh(referral)

        # Create earning
        earning = ReferralEarning(
            referral_id=referral.id,
            amount=Decimal("3.00"),
            paid=False,
        )
        db_session.add(earning)
        await db_session.commit()
        await db_session.refresh(earning)

        # Test properties
        assert earning.is_pending is True
        assert earning.is_paid is False
        assert earning.amount_as_number == 3.0

        # Update to paid
        earning.paid = True
        await db_session.commit()
        await db_session.refresh(earning)

        assert earning.is_pending is False
        assert earning.is_paid is True
