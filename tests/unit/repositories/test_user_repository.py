"""
Unit tests for UserRepository.

Tests data access layer for User model.
"""

import pytest
from decimal import Decimal

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.utils.encryption import hash_password


class TestUserRepositoryCRUD:
    """Tests for basic CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_user(
        self,
        db_session,  # pylint: disable=redefined-outer-name
    ):
        """Test creating a user."""
        repo = UserRepository(db_session)

        user = await repo.create(
            telegram_id=800000001,
            username="testuser",
            wallet_address="0x" + "a" * 40,
            financial_password=hash_password("test123"),
        )

        assert user is not None
        assert user.id is not None
        assert user.telegram_id == 800000001
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_by_id(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test getting user by ID."""
        repo = UserRepository(db_session)

        user = await repo.get_by_id(test_user.id)

        assert user is not None
        assert user.id == test_user.id
        assert user.telegram_id == test_user.telegram_id

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(
        self,
        db_session,  # pylint: disable=redefined-outer-name
    ):
        """Test getting non-existent user by ID."""
        repo = UserRepository(db_session)

        user = await repo.get_by_id(999999999)

        assert user is None

    @pytest.mark.asyncio
    async def test_update_user(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test updating user."""
        repo = UserRepository(db_session)

        updated = await repo.update(
            test_user.id, username="updated_user", balance=Decimal("100")
        )

        assert updated is not None
        assert updated.username == "updated_user"
        assert updated.balance == Decimal("100")

    @pytest.mark.asyncio
    async def test_delete_user(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        create_user_helper,  # pylint: disable=redefined-outer-name
    ):
        """Test deleting user."""
        repo = UserRepository(db_session)

        user = await create_user_helper(telegram_id=800000002)
        user_id = user.id

        deleted = await repo.delete(user_id)

        assert deleted is True

        # Verify deletion
        user = await repo.get_by_id(user_id)
        assert user is None


class TestUserRepositoryQueries:
    """Tests for specific query methods."""

    @pytest.mark.asyncio
    async def test_get_by_telegram_id(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test getting user by Telegram ID."""
        repo = UserRepository(db_session)

        user = await repo.get_by_telegram_id(test_user.telegram_id)

        assert user is not None
        assert user.telegram_id == test_user.telegram_id

    @pytest.mark.asyncio
    async def test_get_by_telegram_id_not_found(
        self,
        db_session,  # pylint: disable=redefined-outer-name
    ):
        """Test getting non-existent user by Telegram ID."""
        repo = UserRepository(db_session)

        user = await repo.get_by_telegram_id(999999999)

        assert user is None

    @pytest.mark.asyncio
    async def test_get_by_wallet_address(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test getting user by wallet address."""
        repo = UserRepository(db_session)

        user = await repo.get_by_wallet_address(test_user.wallet_address)

        assert user is not None
        assert user.wallet_address == test_user.wallet_address

    @pytest.mark.asyncio
    async def test_get_by_wallet_address_not_found(
        self,
        db_session,  # pylint: disable=redefined-outer-name
    ):
        """Test getting non-existent user by wallet address."""
        repo = UserRepository(db_session)

        user = await repo.get_by_wallet_address("0x" + "z" * 40)

        assert user is None

    @pytest.mark.asyncio
    async def test_get_with_referrals(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_referral_chain,  # pylint: disable=redefined-outer-name
    ):
        """Test getting user with referrals loaded."""
        repo = UserRepository(db_session)
        referrer, _, _, _ = test_referral_chain

        user = await repo.get_with_referrals(referrer.id)

        assert user is not None
        assert user.id == referrer.id
        # Referrals should be loaded
        assert hasattr(user, "referrals_as_referrer")

    @pytest.mark.asyncio
    async def test_get_all_telegram_ids(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test getting all Telegram IDs."""
        repo = UserRepository(db_session)

        telegram_ids = await repo.get_all_telegram_ids()

        assert isinstance(telegram_ids, list)
        assert test_user.telegram_id in telegram_ids

    @pytest.mark.asyncio
    async def test_find_by(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test finding users by criteria."""
        repo = UserRepository(db_session)

        users = await repo.find_by(is_verified=False)

        assert isinstance(users, list)
        assert any(u.id == test_user.id for u in users)

    @pytest.mark.asyncio
    async def test_count(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test counting users."""
        repo = UserRepository(db_session)

        count = await repo.count()

        assert isinstance(count, int)
        assert count >= 1

