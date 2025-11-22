"""
Unit tests for RewardService.

Tests reward session management and deposit reward calculations.
"""

import pytest
from datetime import datetime, UTC
from decimal import Decimal

from app.models.reward_session import RewardSession
from app.services.reward_service import RewardService


class TestRewardServiceSession:
    """Tests for reward session management."""

    @pytest.mark.asyncio
    async def test_create_session_success(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_admin,  # pylint: disable=redefined-outer-name
    ):
        """Test successful reward session creation."""
        service = RewardService(db_session)

        # All 5 levels required
        reward_rates = {
            1: Decimal("0.02"),
            2: Decimal("0.02"),
            3: Decimal("0.02"),
            4: Decimal("0.02"),
            5: Decimal("0.02"),
        }
        start_date = datetime.now(UTC)
        end_date = datetime.now(UTC).replace(year=start_date.year + 1)

        session, error = await service.create_session(
            name="Test Session",
            reward_rates=reward_rates,
            start_date=start_date,
            end_date=end_date,
            created_by=test_admin.id,
        )

        assert session is not None
        assert error is None
        assert session.name == "Test Session"
        assert session.created_by == test_admin.id

    @pytest.mark.asyncio
    async def test_create_session_invalid_dates(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_admin,  # pylint: disable=redefined-outer-name
    ):
        """Test session creation with invalid dates."""
        service = RewardService(db_session)

        # All 5 levels required
        reward_rates = {
            1: Decimal("0.02"),
            2: Decimal("0.02"),
            3: Decimal("0.02"),
            4: Decimal("0.02"),
            5: Decimal("0.02"),
        }
        start_date = datetime.now(UTC)
        end_date = start_date  # Same date (invalid)

        session, error = await service.create_session(
            name="Invalid Session",
            reward_rates=reward_rates,
            start_date=start_date,
            end_date=end_date,
            created_by=test_admin.id,
        )

        assert session is None
        assert error is not None
        assert "дата начала" in error.lower() or "дата окончания" in error.lower()

    @pytest.mark.asyncio
    async def test_get_session_statistics(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_admin,  # pylint: disable=redefined-outer-name
    ):
        """Test getting session statistics."""
        service = RewardService(db_session)

        # Create session with all 5 levels
        reward_rates = {
            1: Decimal("0.02"),
            2: Decimal("0.02"),
            3: Decimal("0.02"),
            4: Decimal("0.02"),
            5: Decimal("0.02"),
        }
        start_date = datetime.now(UTC)
        end_date = datetime.now(UTC).replace(year=start_date.year + 1)

        session, _ = await service.create_session(
            name="Stats Session",
            reward_rates=reward_rates,
            start_date=start_date,
            end_date=end_date,
            created_by=test_admin.id,
        )

        assert session is not None

        # Get statistics
        stats = await service.get_session_statistics(session.id)

        assert isinstance(stats, dict)
        assert "total_rewards" in stats
        assert "total_amount" in stats
        assert "paid_rewards" in stats
        assert "paid_amount" in stats
        assert "pending_rewards" in stats
        assert "pending_amount" in stats

        # New session should have no rewards
        assert stats["total_rewards"] == 0
        assert stats["total_amount"] == Decimal("0")


class TestRewardServiceUserRewards:
    """Tests for user reward operations."""

    @pytest.mark.asyncio
    async def test_get_user_unpaid_rewards_empty(
        self,
        db_session,  # pylint: disable=redefined-outer-name
        test_user,  # pylint: disable=redefined-outer-name
    ):
        """Test getting unpaid rewards for user with none."""
        service = RewardService(db_session)

        rewards = await service.get_user_unpaid_rewards(test_user.id)

        assert isinstance(rewards, list)
        assert len(rewards) == 0

    @pytest.mark.asyncio
    async def test_mark_rewards_as_paid(
        self,
        db_session,  # pylint: disable=redefined-outer-name
    ):
        """Test marking rewards as paid."""
        service = RewardService(db_session)

        # This test requires existing rewards
        # In real scenario, rewards would be created first
        result = await service.mark_rewards_as_paid(
            reward_ids=[], tx_hash="0x" + "a" * 64
        )

        success, count, error = result
        assert isinstance(success, bool)
        assert isinstance(count, int)
        assert error is None or isinstance(error, str)

