"""
Unit tests for DepositRepository.

Tests data access layer for Deposit model.
"""

import pytest
from decimal import Decimal

from app.models.deposit import Deposit
from app.models.enums import TransactionStatus
from app.repositories.deposit_repository import DepositRepository


class TestDepositRepositoryCRUD:
    """Tests for basic CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_deposit(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test creating a deposit."""
        repo = DepositRepository(db_session)

        deposit = await repo.create(
            user_id=test_user.id,
            level=1,
            amount=Decimal("10"),
            roi_cap_amount=Decimal("50"),
            roi_paid_amount=Decimal("0"),
            status=TransactionStatus.PENDING.value,
        )

        assert deposit is not None
        assert deposit.id is not None
        assert deposit.user_id == test_user.id
        assert deposit.level == 1
        assert deposit.amount == Decimal("10")

    @pytest.mark.asyncio
    async def test_get_by_id(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_deposit,  # pylint: disable=redefined-outer-name
    ):
        """Test getting deposit by ID."""
        repo = DepositRepository(db_session)

        deposit = await repo.get_by_id(test_deposit.id)

        assert deposit is not None
        assert deposit.id == test_deposit.id

    @pytest.mark.asyncio
    async def test_get_by_user(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
        create_deposit_helper,  # pylint: disable=redefined-outer-name
    ):
        """Test getting deposits by user."""
        repo = DepositRepository(db_session)

        # Create multiple deposits
        await create_deposit_helper(test_user, level=1)
        await create_deposit_helper(test_user, level=2)

        deposits = await repo.get_by_user(test_user.id)

        assert isinstance(deposits, list)
        assert len(deposits) >= 2
        assert all(d.user_id == test_user.id for d in deposits)

    @pytest.mark.asyncio
    async def test_get_total_deposited(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
        create_deposit_helper,  # pylint: disable=redefined-outer-name
    ):
        """Test getting total deposited amount."""
        repo = DepositRepository(db_session)

        # Create deposits
        await create_deposit_helper(
            test_user, level=1, amount=Decimal("10"), status="confirmed"
        )
        await create_deposit_helper(
            test_user, level=2, amount=Decimal("50"), status="confirmed"
        )

        total = await repo.get_total_deposited(test_user.id)

        assert total >= Decimal("60")

    @pytest.mark.asyncio
    async def test_update_deposit(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_deposit,  # pylint: disable=redefined-outer-name
    ):
        """Test updating deposit."""
        repo = DepositRepository(db_session)

        updated = await repo.update(
            test_deposit.id,
            status=TransactionStatus.CONFIRMED.value,
            roi_paid_amount=Decimal("10"),
        )

        assert updated is not None
        assert updated.status == TransactionStatus.CONFIRMED.value
        assert updated.roi_paid_amount == Decimal("10")

