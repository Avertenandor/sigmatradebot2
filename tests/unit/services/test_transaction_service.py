"""
Unit tests for TransactionService.

Tests unified transaction history across all types.
"""

import pytest
from decimal import Decimal

from app.models.enums import TransactionStatus, TransactionType
from app.services.transaction_service import TransactionService


class TestTransactionServiceGetAll:
    """Tests for getting all transactions."""

    @pytest.mark.asyncio
    async def test_get_all_transactions_empty(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test getting transactions for user with no transactions."""
        service = TransactionService(db_session)

        result = await service.get_all_transactions(
            user_id=test_user.id, limit=20, offset=0
        )

        assert isinstance(result, dict)
        assert "transactions" in result
        assert "total" in result
        assert "has_more" in result
        assert len(result["transactions"]) == 0
        assert result["total"] == 0
        assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_get_all_transactions_with_deposit(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
        create_deposit_helper,  # pylint: disable=redefined-outer-name
    ):
        """Test getting transactions including deposits."""
        service = TransactionService(db_session)

        # Create deposit
        deposit = await create_deposit_helper(
            test_user, level=1, amount=Decimal("10"), status="confirmed"
        )

        result = await service.get_all_transactions(
            user_id=test_user.id, limit=20, offset=0
        )

        assert result["total"] >= 1
        assert len(result["transactions"]) >= 1
        # Check that deposit is in transactions
        deposit_ids = [
            t.id for t in result["transactions"]
            if t.type == TransactionType.DEPOSIT
        ]
        assert f"deposit:{deposit.id}" in deposit_ids

    @pytest.mark.asyncio
    async def test_get_all_transactions_with_type_filter(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
        create_deposit_helper,  # pylint: disable=redefined-outer-name
    ):
        """Test filtering transactions by type."""
        service = TransactionService(db_session)

        # Create deposit
        await create_deposit_helper(
            test_user, level=1, amount=Decimal("10"), status="confirmed"
        )

        # Get only deposits
        result = await service.get_all_transactions(
            user_id=test_user.id,
            limit=20,
            offset=0,
            transaction_type=TransactionType.DEPOSIT,
        )

        assert all(
            t.type == TransactionType.DEPOSIT
            for t in result["transactions"]
        )

    @pytest.mark.asyncio
    async def test_get_all_transactions_with_status_filter(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
        create_deposit_helper,  # pylint: disable=redefined-outer-name
    ):
        """Test filtering transactions by status."""
        service = TransactionService(db_session)

        # Create confirmed deposit
        await create_deposit_helper(
            test_user, level=1, amount=Decimal("10"), status="confirmed"
        )

        # Get only confirmed transactions
        result = await service.get_all_transactions(
            user_id=test_user.id,
            limit=20,
            offset=0,
            status=TransactionStatus.CONFIRMED,
        )

        assert all(
            t.status == TransactionStatus.CONFIRMED
            for t in result["transactions"]
        )

    @pytest.mark.asyncio
    async def test_get_all_transactions_pagination(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
        create_deposit_helper,  # pylint: disable=redefined-outer-name
    ):
        """Test transaction pagination."""
        service = TransactionService(db_session)

        # Create multiple deposits
        for i in range(5):
            await create_deposit_helper(
                test_user,
                level=1,
                amount=Decimal("10"),
                status="confirmed",
            )

        # Get first page
        result1 = await service.get_all_transactions(
            user_id=test_user.id, limit=2, offset=0
        )

        assert len(result1["transactions"]) <= 2
        assert result1["has_more"] is True or result1["total"] <= 2

        # Get second page
        result2 = await service.get_all_transactions(
            user_id=test_user.id, limit=2, offset=2
        )

        assert len(result2["transactions"]) <= 2


class TestTransactionServiceStats:
    """Tests for transaction statistics."""

    @pytest.mark.asyncio
    async def test_get_transaction_stats_empty(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test getting stats for user with no transactions."""
        service = TransactionService(db_session)

        stats = await service.get_transaction_stats(user_id=test_user.id)

        assert isinstance(stats, dict)
        assert "total_deposits" in stats
        assert "total_withdrawals" in stats
        assert "confirmed_withdrawals" in stats
        assert "pending_withdrawals" in stats
        assert "total_referral_earnings" in stats
        assert "pending_referral_earnings" in stats

        assert stats["total_deposits"] == Decimal("0")
        assert stats["total_withdrawals"] == Decimal("0")

    @pytest.mark.asyncio
    async def test_get_transaction_stats_with_deposits(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
        create_deposit_helper,  # pylint: disable=redefined-outer-name
    ):
        """Test getting stats with deposits."""
        service = TransactionService(db_session)

        # Create deposits
        await create_deposit_helper(
            test_user, level=1, amount=Decimal("10"), status="confirmed"
        )
        await create_deposit_helper(
            test_user, level=2, amount=Decimal("50"), status="confirmed"
        )

        stats = await service.get_transaction_stats(user_id=test_user.id)

        assert stats["total_deposits"] == Decimal("60")

