"""
Unit tests for UserService.

Tests user registration, profile management, and referral handling.
"""

import pytest
from decimal import Decimal

from app.models.user import User
from app.services.user_service import UserService
from app.utils.encryption import hash_password, verify_password


class TestUserServiceRegistration:
    """Tests for user registration."""

    @pytest.mark.asyncio
    async def test_register_user_success(
        self,
        db_session,  # pylint: disable=redefined-outer-name
    ):
        """Test successful user registration."""
        service = UserService(db_session)

        # Note: register_user expects hashed password
        hashed_password = hash_password("test123")
        user = await service.register_user(
            telegram_id=700000001,
            wallet_address="0x" + "a" * 40,
            financial_password=hashed_password,
            username="testuser",
        )

        assert user is not None
        assert user.telegram_id == 700000001
        assert user.username == "testuser"
        assert user.wallet_address == "0x" + "a" * 40
        assert verify_password("test123", user.financial_password)
        assert user.balance == Decimal("0")
        assert user.is_verified is False
        assert user.is_banned is False

    @pytest.mark.asyncio
    async def test_register_user_with_referrer(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        create_user_helper,  # pylint: disable=redefined-outer-name
    ):
        """Test user registration with referrer."""
        service = UserService(db_session)

        # Create referrer
        referrer = await create_user_helper(telegram_id=700000002)

        # Register new user with referrer
        hashed_password = hash_password("test456")
        user = await service.register_user(
            telegram_id=700000003,
            wallet_address="0x" + "b" * 40,
            financial_password=hashed_password,
            referrer_telegram_id=referrer.telegram_id,
        )

        assert user is not None
        assert user.referrer_id == referrer.id

    @pytest.mark.asyncio
    async def test_register_duplicate_telegram_id_fails(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test that duplicate telegram_id registration fails."""
        service = UserService(db_session)

        hashed_password = hash_password("test789")
        with pytest.raises(ValueError, match="already registered"):
            await service.register_user(
                telegram_id=test_user.telegram_id,
                wallet_address="0x" + "c" * 40,
                financial_password=hashed_password,
            )


class TestUserServiceGetters:
    """Tests for user getter methods."""

    @pytest.mark.asyncio
    async def test_get_by_id_success(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test getting user by ID."""
        service = UserService(db_session)

        user = await service.get_by_id(test_user.id)

        assert user is not None
        assert user.id == test_user.id
        assert user.telegram_id == test_user.telegram_id

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(
        self,
        db_session,  # pylint: disable=redefined-outer-name
    ):
        """Test getting non-existent user by ID."""
        service = UserService(db_session)

        user = await service.get_by_id(999999999)

        assert user is None

    @pytest.mark.asyncio
    async def test_get_by_telegram_id_success(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test getting user by Telegram ID."""
        service = UserService(db_session)

        user = await service.get_by_telegram_id(test_user.telegram_id)

        assert user is not None
        assert user.telegram_id == test_user.telegram_id

    @pytest.mark.asyncio
    async def test_get_by_telegram_id_not_found(
        self,
        db_session,  # pylint: disable=redefined-outer-name
    ):
        """Test getting non-existent user by Telegram ID."""
        service = UserService(db_session)

        user = await service.get_by_telegram_id(999999999)

        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_id_alias(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test that get_user_by_id is alias for get_by_id."""
        service = UserService(db_session)

        user1 = await service.get_by_id(test_user.id)
        user2 = await service.get_user_by_id(test_user.id)

        assert user1 is not None
        assert user2 is not None
        assert user1.id == user2.id


class TestUserServiceVerification:
    """Tests for user verification."""

    @pytest.mark.asyncio
    async def test_update_profile_verification(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test updating user profile to verified."""
        service = UserService(db_session)

        assert test_user.is_verified is False

        updated = await service.update_profile(
            test_user.id, is_verified=True
        )

        assert updated is not None
        await db_session.refresh(test_user)
        assert test_user.is_verified is True


class TestUserServiceBanning:
    """Tests for user banning."""

    @pytest.mark.asyncio
    async def test_ban_user_success(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test successful user ban."""
        service = UserService(db_session)

        assert test_user.is_banned is False

        updated = await service.ban_user(test_user.id, ban=True)

        assert updated is not None
        await db_session.refresh(test_user)
        assert test_user.is_banned is True

    @pytest.mark.asyncio
    async def test_unban_user_success(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test successful user unban."""
        service = UserService(db_session)

        # First ban
        test_user.is_banned = True
        await db_session.commit()

        result = await service.unban_user(test_user.id)

        assert result["success"] is True
        await db_session.refresh(test_user)
        assert test_user.is_banned is False


class TestUserServiceBalance:
    """Tests for user balance operations."""

    @pytest.mark.asyncio
    async def test_get_user_balance(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test getting user balance statistics."""
        service = UserService(db_session)

        balance_info = await service.get_user_balance(test_user.id)

        assert isinstance(balance_info, dict)
        assert "available_balance" in balance_info
        assert "total_balance" in balance_info
        assert "total_earned" in balance_info
        assert "pending_earnings" in balance_info
        assert "pending_withdrawals" in balance_info
        assert "total_deposits" in balance_info
        assert "total_withdrawals" in balance_info
        assert "total_earnings" in balance_info

    @pytest.mark.asyncio
    async def test_get_user_balance_nonexistent_user(
        self,
        db_session,  # pylint: disable=redefined-outer-name
    ):
        """Test getting balance for non-existent user."""
        service = UserService(db_session)

        balance_info = await service.get_user_balance(999999999)

        assert balance_info["available_balance"] == Decimal("0.00")
        assert balance_info["total_balance"] == Decimal("0.00")


class TestUserServiceStats:
    """Tests for user statistics."""

    @pytest.mark.asyncio
    async def test_get_user_stats(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test getting user statistics."""
        service = UserService(db_session)

        stats = await service.get_user_stats(test_user.id)

        assert isinstance(stats, dict)
        assert "total_deposits" in stats
        assert "referral_count" in stats
        assert "activated_levels" in stats

    @pytest.mark.asyncio
    async def test_get_user_stats_nonexistent_user(
        self,
        db_session,  # pylint: disable=redefined-outer-name
    ):
        """Test getting stats for non-existent user."""
        service = UserService(db_session)

        stats = await service.get_user_stats(999999999)

        assert stats == {}

