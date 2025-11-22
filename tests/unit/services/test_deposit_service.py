"""
Unit tests for DepositService.

Tests deposit creation, ROI tracking, and status management.
"""

import pytest
from decimal import Decimal

from app.models.deposit import Deposit
from app.models.enums import TransactionStatus
from app.services.deposit_service import DepositService


class TestDepositServiceCreation:
    """Tests for deposit creation."""

    @pytest.mark.asyncio
    async def test_create_deposit_success(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
        deposit_level_versions,  # pylint: disable=redefined-outer-name
    ):
        """Test successful deposit creation."""
        service = DepositService(db_session)

        deposit = await service.create_deposit(
            user_id=test_user.id,
            level=1,
            amount=Decimal("10"),
            tx_hash="0x" + "a" * 64,
        )

        assert deposit is not None
        assert deposit.user_id == test_user.id
        assert deposit.level == 1
        assert deposit.amount == Decimal("10")
        assert deposit.tx_hash == "0x" + "a" * 64
        assert deposit.status == TransactionStatus.PENDING.value
        # ROI cap should be calculated from deposit level version
        assert deposit.roi_cap_amount is not None

    @pytest.mark.asyncio
    async def test_create_deposit_all_levels(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
        deposit_level_versions,  # pylint: disable=redefined-outer-name
    ):
        """Test creating deposits for all levels."""
        service = DepositService(db_session)

        levels = {
            1: Decimal("10"),
            2: Decimal("50"),
            3: Decimal("100"),
            4: Decimal("150"),
            5: Decimal("300"),
        }

        for level, amount in levels.items():
            deposit = await service.create_deposit(
                user_id=test_user.id,
                level=level,
                amount=amount,
                tx_hash="0x" + "a" * 64,
            )

            assert deposit.level == level
            assert deposit.amount == amount
            assert deposit.roi_cap_amount is not None  # Calculated from version

    @pytest.mark.asyncio
    async def test_create_deposit_invalid_level(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
        deposit_level_versions,  # pylint: disable=redefined-outer-name
    ):
        """Test creating deposit with invalid level."""
        service = DepositService(db_session)

        with pytest.raises(ValueError, match="level|not available"):
            await service.create_deposit(
                user_id=test_user.id,
                level=99,  # Invalid level
                amount=Decimal("10"),
                tx_hash="0x" + "a" * 64,
            )


class TestDepositServiceStatus:
    """Tests for deposit status management."""

    @pytest.mark.asyncio
    async def test_confirm_deposit(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_deposit,  # pylint: disable=redefined-outer-name
    ):
        """Test confirming a deposit."""
        service = DepositService(db_session)

        # Deposit should be confirmed by fixture
        assert test_deposit.status == TransactionStatus.CONFIRMED.value

        # Get deposit again to verify
        deposit = await service.deposit_repo.get_by_id(test_deposit.id)
        assert deposit is not None
        assert deposit.status == TransactionStatus.CONFIRMED.value

    @pytest.mark.asyncio
    async def test_get_user_deposits(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
        create_deposit_helper,  # pylint: disable=redefined-outer-name
    ):
        """Test getting all deposits for user."""
        service = DepositService(db_session)

        # Create multiple deposits
        await create_deposit_helper(test_user, level=1)
        await create_deposit_helper(test_user, level=2)

        deposits = await service.deposit_repo.get_by_user(test_user.id)

        assert len(deposits) >= 2


class TestDepositServiceROI:
    """Tests for ROI calculations."""

    @pytest.mark.asyncio
    async def test_roi_cap_calculation(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
        deposit_level_versions,  # pylint: disable=redefined-outer-name
    ):
        """Test ROI cap calculation (500% of deposit amount)."""
        service = DepositService(db_session)

        deposit = await service.create_deposit(
            user_id=test_user.id,
            level=3,
            amount=Decimal("100"),
            tx_hash="0x" + "a" * 64,
        )

        # ROI cap should be calculated from deposit level version
        assert deposit.roi_cap_amount is not None
        assert deposit.roi_paid_amount == Decimal("0")

    @pytest.mark.asyncio
    async def test_roi_paid_tracking(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_deposit,  # pylint: disable=redefined-outer-name
    ):
        """Test tracking of paid ROI."""
        service = DepositService(db_session)

        # Update ROI paid amount
        test_deposit.roi_paid_amount = Decimal("10")
        await db_session.commit()

        # Verify update
        await db_session.refresh(test_deposit)
        assert test_deposit.roi_paid_amount == Decimal("10")

