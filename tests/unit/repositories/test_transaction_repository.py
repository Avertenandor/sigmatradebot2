"""
Unit tests for TransactionRepository.

Tests data access layer for Transaction model.
"""

import pytest
from decimal import Decimal

from app.models.enums import TransactionStatus, TransactionType
from app.models.transaction import Transaction
from app.repositories.transaction_repository import TransactionRepository


class TestTransactionRepositoryCRUD:
    """Tests for basic CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_transaction(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test creating a transaction."""
        repo = TransactionRepository(db_session)

        transaction = await repo.create(
            user_id=test_user.id,
            type=TransactionType.DEPOSIT.value,
            amount=Decimal("100"),
            balance_before=Decimal("0"),
            balance_after=Decimal("100"),
            status=TransactionStatus.PENDING.value,
            description="Test deposit",
        )

        assert transaction is not None
        assert transaction.id is not None
        assert transaction.user_id == test_user.id
        assert transaction.amount == Decimal("100")

    @pytest.mark.asyncio
    async def test_get_by_id(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_transaction,  # pylint: disable=redefined-outer-name
    ):
        """Test getting transaction by ID."""
        repo = TransactionRepository(db_session)

        transaction = await repo.get_by_id(test_transaction.id)

        assert transaction is not None
        assert transaction.id == test_transaction.id

    @pytest.mark.asyncio
    async def test_get_by_user(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
        create_transaction_helper,  # pylint: disable=redefined-outer-name
    ):
        """Test getting transactions by user."""
        repo = TransactionRepository(db_session)

        # Create multiple transactions
        await create_transaction_helper(
            test_user, transaction_type="deposit", amount=Decimal("10")
        )
        await create_transaction_helper(
            test_user, transaction_type="withdrawal", amount=Decimal("5")
        )

        transactions = await repo.get_by_user(test_user.id)

        assert isinstance(transactions, list)
        assert len(transactions) >= 2
        assert all(t.user_id == test_user.id for t in transactions)

    @pytest.mark.asyncio
    async def test_update_transaction(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_transaction,  # pylint: disable=redefined-outer-name
    ):
        """Test updating transaction."""
        repo = TransactionRepository(db_session)

        updated = await repo.update(
            test_transaction.id,
            status=TransactionStatus.CONFIRMED.value,
        )

        assert updated is not None
        assert updated.status == TransactionStatus.CONFIRMED.value

