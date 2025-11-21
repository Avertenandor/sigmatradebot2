"""
Reward service.

Manages reward sessions and deposit reward calculations with ROI caps.
"""

from datetime import datetime
from decimal import Decimal

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deposit import Deposit
from app.models.deposit_reward import DepositReward
from app.models.enums import TransactionStatus
from app.models.reward_session import RewardSession
from app.repositories.deposit_repository import DepositRepository
from app.repositories.deposit_reward_repository import (
    DepositRewardRepository,
)
from app.repositories.reward_session_repository import (
    RewardSessionRepository,
)


class RewardService:
    """Reward service for managing reward sessions and calculations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize reward service."""
        self.session = session
        self.session_repo = RewardSessionRepository(session)
        self.reward_repo = DepositRewardRepository(session)
        self.deposit_repo = DepositRepository(session)

    async def create_session(
        self,
        name: str,
        reward_rates: dict[int, Decimal],
        start_date: datetime,
        end_date: datetime,
        created_by: int,
    ) -> tuple[RewardSession | None, str | None]:
        """
        Create new reward session.

        Args:
            name: Session name
            reward_rates: Dict of {level: rate} (e.g., {1: 1.117})
            start_date: Start date
            end_date: End date
            created_by: Admin ID who created session

        Returns:
            Tuple of (session, error_message)
        """
        # Validate dates
        if start_date >= end_date:
            return None, "Дата начала должна быть раньше даты окончания"

        # Validate reward rates for all 5 levels
        for level in range(1, 6):
            if level not in reward_rates or reward_rates[level] < 0:
                return None, f"Некорректная ставка для уровня {level}"

        # Create session
        session = await self.session_repo.create(
            name=name,
            reward_rate_level_1=reward_rates[1],
            reward_rate_level_2=reward_rates[2],
            reward_rate_level_3=reward_rates[3],
            reward_rate_level_4=reward_rates[4],
            reward_rate_level_5=reward_rates[5],
            start_date=start_date,
            end_date=end_date,
            is_active=True,
            created_by=created_by,
        )

        await self.session.commit()

        logger.info(
            "Reward session created",
            extra={
                "session_id": session.id,
                "name": name,
                "created_by": created_by,
            },
        )

        return session, None

    async def update_session(
        self,
        session_id: int,
        name: str | None = None,
        reward_rates: dict[int, Decimal] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        is_active: bool | None = None,
    ) -> tuple[bool, str | None]:
        """
        Update reward session.

        Args:
            session_id: Session ID
            name: New name (optional)
            reward_rates: New rates (optional)
            start_date: New start date (optional)
            end_date: New end date (optional)
            is_active: New active status (optional)

        Returns:
            Tuple of (success, error_message)
        """
        session_obj = await self.session_repo.get_by_id(session_id)

        if not session_obj:
            return False, "Сессия не найдена"

        # Build update dict
        updates = {}
        if name:
            updates["name"] = name
        if start_date:
            updates["start_date"] = start_date
        if end_date:
            updates["end_date"] = end_date
        if is_active is not None:
            updates["is_active"] = is_active

        # Update reward rates if provided
        if reward_rates:
            for level, rate in reward_rates.items():
                updates[f"reward_rate_level_{level}"] = rate

        # Apply updates
        if updates:
            await self.session_repo.update(session_id, **updates)

        # Validate dates
        updated = await self.session_repo.get_by_id(session_id)
        if updated and updated.start_date >= updated.end_date:
            await self.session.rollback()
            return False, "Дата начала должна быть раньше даты окончания"

        await self.session.commit()

        logger.info(
            "Reward session updated", extra={"session_id": session_id}
        )

        return True, None

    async def delete_session(
        self, session_id: int
    ) -> tuple[bool, str | None]:
        """
        Delete reward session (only if no rewards calculated).

        Args:
            session_id: Session ID

        Returns:
            Tuple of (success, error_message)
        """
        # Check if rewards have been calculated
        rewards_count = len(
            await self.reward_repo.find_by(
                reward_session_id=session_id
            )
        )

        if rewards_count > 0:
            return False, (
                f"Невозможно удалить сессию с {rewards_count} "
                f"начисленными наградами. "
                f"Деактивируйте сессию вместо удаления."
            )

        # Delete session
        await self.session_repo.delete(session_id)
        await self.session.commit()

        logger.info(
            "Reward session deleted", extra={"session_id": session_id}
        )

        return True, None

    async def get_all_sessions(self) -> list[RewardSession]:
        """Get all reward sessions."""
        return await self.session_repo.find_all()

    async def get_active_sessions(self) -> list[RewardSession]:
        """Get active reward sessions."""
        return await self.session_repo.get_active_sessions()

    async def get_session_by_id(
        self, session_id: int
    ) -> RewardSession | None:
        """Get reward session by ID."""
        return await self.session_repo.get_by_id(session_id)

    async def calculate_rewards_for_session(  # noqa: C901
        self, session_id: int
    ) -> tuple[bool, int, Decimal, str | None]:
        """
        Calculate rewards for session.

        CRITICAL: Respects ROI cap (500% for level 1).
        Skips deposits with earnings_blocked flag.

        Args:
            session_id: Session ID

        Returns:
            Tuple of (success, rewards_calculated, total_amount, error)
        """
        session_obj = await self.get_session_by_id(session_id)

        if not session_obj:
            return False, 0, Decimal("0"), "Сессия не найдена"

        if not session_obj.is_active:
            return False, 0, Decimal("0"), "Сессия неактивна"

        # R9-2: Find deposits in session period with pessimistic lock
        # This prevents race conditions with withdrawal operations
        stmt = (
            select(Deposit)
            .where(
                Deposit.status == TransactionStatus.CONFIRMED.value,
                Deposit.confirmed_at >= session_obj.start_date,
                Deposit.confirmed_at <= session_obj.end_date,
            )
            .with_for_update()  # Lock deposits to prevent concurrent modifications
        )

        result = await self.session.execute(stmt)
        deposits = list(result.scalars().all())

        logger.info(
            "Calculating rewards for session",
            extra={
                "session_id": session_id,
                "deposits_found": len(deposits),
            },
        )

        rewards_calculated = 0
        total_reward_amount = Decimal("0")

        for deposit in deposits:
            # Load user to check earnings_blocked
            user_stmt = select(deposit.user)
            user_result = await self.session.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            # CRITICAL: Skip if earnings blocked (finpass recovery)
            if user and user.earnings_blocked:
                logger.warning(
                    "Skipped deposit reward - earnings blocked",
                    extra={
                        "user_id": deposit.user_id,
                        "deposit_id": deposit.id,
                        "reason": "finpass_recovery_in_progress",
                    },
                )
                continue

            # R15-1: Skip if user is banned (stop ROI distribution)
            if user and user.is_banned:
                logger.warning(
                    "Skipped deposit reward - user banned",
                    extra={
                        "user_id": deposit.user_id,
                        "deposit_id": deposit.id,
                        "reason": "user_blocked",
                    },
                )
                continue

            # Check if reward already calculated
            existing = await self.reward_repo.find_by(
                deposit_id=deposit.id, reward_session_id=session_id
            )

            if existing:
                continue

            # R12-1: Check ROI cap for all levels (not just Level 1)
            if deposit.is_roi_completed:
                logger.info(
                    "Skipped reward - ROI cap reached",
                    extra={
                        "deposit_id": deposit.id,
                        "level": deposit.level,
                        "roi_cap": str(deposit.roi_cap_amount),
                        "roi_paid": str(deposit.roi_paid_amount),
                    },
                )
                continue

            # R17-1: Get reward rate - use RewardSession if available, otherwise use deposit_version
            reward_rate = session_obj.get_reward_rate_for_level(
                deposit.level
            )

            # If RewardSession rate is 0 or deposit has version, use version's roi_percent
            if reward_rate == Decimal("0") or (deposit.deposit_version and deposit.deposit_version.roi_percent):
                # R17-1: Use deposit version's roi_percent as fallback/base rate
                if deposit.deposit_version:
                    # Convert roi_percent to daily rate (assuming roi_percent is annual)
                    # For now, use roi_percent directly if it's already daily
                    version_rate = deposit.deposit_version.roi_percent
                    # If RewardSession rate is 0, use version rate
                    if reward_rate == Decimal("0"):
                        reward_rate = version_rate
                    # Otherwise, RewardSession overrides (temporary promotion)
                elif reward_rate == Decimal("0"):
                    # No version and no session rate - skip
                    logger.warning(
                        f"No reward rate available for deposit {deposit.id}",
                        extra={"deposit_id": deposit.id, "level": deposit.level},
                    )
                    continue

            # Calculate reward
            reward_amount = (deposit.amount * reward_rate) / 100

            # R12-1: For all levels, cap to remaining ROI space
            if deposit.roi_cap_amount:
                roi_remaining = (
                    deposit.roi_cap_amount -
                    (deposit.roi_paid_amount or Decimal("0"))
                )

                if reward_amount > roi_remaining:
                    logger.warning(
                        "Reward capped to remaining ROI",
                        extra={
                            "deposit_id": deposit.id,
                            "level": deposit.level,
                            "original_reward": str(reward_amount),
                            "capped_reward": str(roi_remaining),
                        },
                    )
                    reward_amount = roi_remaining

                if reward_amount <= 0:
                    continue

            # Create reward record
            await self.reward_repo.create(
                user_id=deposit.user_id,
                deposit_id=deposit.id,
                reward_session_id=session_id,
                deposit_level=deposit.level,
                deposit_amount=deposit.amount,
                reward_rate=reward_rate,
                reward_amount=reward_amount,
                paid=False,
            )

            # R12-1: Update deposit roi_paid_amount and check for completion
            from app.repositories.deposit_repository import DepositRepository
            from datetime import UTC, datetime

            deposit_repo = DepositRepository(self.session)
            new_roi_paid = (deposit.roi_paid_amount or Decimal("0")) + reward_amount

            # Update roi_paid_amount
            await deposit_repo.update(
                deposit.id,
                roi_paid_amount=new_roi_paid,
            )

            # R12-1: Check if ROI cap reached for all levels
            if deposit.roi_cap_amount and new_roi_paid >= deposit.roi_cap_amount:
                # Mark deposit as ROI completed with timestamp
                from datetime import UTC, datetime
                await deposit_repo.update(
                    deposit.id,
                    is_roi_completed=True,
                    completed_at=datetime.now(UTC),
                )
                logger.info(
                    "Deposit ROI completed (cap reached)",
                    extra={
                        "deposit_id": deposit.id,
                        "user_id": deposit.user_id,
                        "level": deposit.level,
                        "roi_paid": str(new_roi_paid),
                        "roi_cap": str(deposit.roi_cap_amount),
                    },
                )

            rewards_calculated += 1
            total_reward_amount += reward_amount

        await self.session.commit()

        logger.info(
            "Rewards calculation completed",
            extra={
                "session_id": session_id,
                "rewards_calculated": rewards_calculated,
                "total_amount": str(total_reward_amount),
            },
        )

        return True, rewards_calculated, total_reward_amount, None

    async def get_session_statistics(
        self, session_id: int
    ) -> dict:
        """
        Get session statistics.

        Args:
            session_id: Session ID

        Returns:
            Dict with comprehensive session stats
        """
        # Get all rewards for session
        rewards = await self.reward_repo.find_by(
            reward_session_id=session_id
        )

        total_rewards = len(rewards)
        paid_rewards = len([r for r in rewards if r.paid])
        pending_rewards = total_rewards - paid_rewards

        total_amount = sum(r.reward_amount for r in rewards)
        paid_amount = sum(r.reward_amount for r in rewards if r.paid)
        pending_amount = total_amount - paid_amount

        return {
            "total_rewards": total_rewards,
            "total_amount": total_amount,
            "paid_rewards": paid_rewards,
            "paid_amount": paid_amount,
            "pending_rewards": pending_rewards,
            "pending_amount": pending_amount,
        }

    async def get_user_unpaid_rewards(
        self, user_id: int
    ) -> list[DepositReward]:
        """Get unpaid rewards for user."""
        return await self.reward_repo.get_unpaid_by_user(user_id)

    async def mark_rewards_as_paid(
        self, reward_ids: list[int], tx_hash: str
    ) -> tuple[bool, int, str | None]:
        """
        Mark rewards as paid (bulk operation).

        Args:
            reward_ids: List of reward IDs
            tx_hash: Transaction hash

        Returns:
            Tuple of (success, updated_count, error_message)
        """
        updated = 0

        for reward_id in reward_ids:
            result = await self.reward_repo.update(
                reward_id, paid=True, tx_hash=tx_hash
            )
            if result:
                updated += 1

        await self.session.commit()

        logger.info(
            "Rewards marked as paid",
            extra={
                "reward_ids": reward_ids,
                "tx_hash": tx_hash,
                "updated": updated,
            },
        )

        return True, updated, None
