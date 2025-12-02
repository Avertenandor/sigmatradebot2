"""
Deposit service.

Business logic for deposit management and ROI tracking.
"""

from decimal import Decimal

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from typing import Any

from decimal import Decimal

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.deposit import Deposit
from app.models.enums import TransactionStatus
from app.repositories.deposit_repository import DepositRepository
from app.repositories.user_repository import UserRepository


class DepositService:
    """Deposit service handles deposit lifecycle and ROI."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize deposit service."""
        self.session = session
        self.deposit_repo = DepositRepository(session)
        self.user_repo = UserRepository(session)

    async def create_deposit(
        self,
        user_id: int,
        level: int,
        amount: Decimal,
        tx_hash: str | None = None,
        redis_client: Any | None = None,
    ) -> Deposit:
        """
        Create new deposit with proper error handling.

        R15-5: Uses distributed lock to prevent race conditions.

        Args:
            user_id: User ID
            level: Deposit level (1-5)
            amount: Deposit amount
            tx_hash: Blockchain transaction hash
            redis_client: Optional Redis client for distributed lock

        Returns:
            Created deposit

        Raises:
            ValueError: If level or amount is invalid
        """
        # R15-5: Use distributed lock to prevent race conditions
        from app.utils.distributed_lock import get_distributed_lock

        lock = get_distributed_lock(
            redis_client=redis_client, session=self.session
        )
        lock_key = f"user:{user_id}:create_deposit"

        async with lock.lock(lock_key, timeout=30, blocking=True, blocking_timeout=5.0) as acquired:
            if not acquired:
                logger.warning(
                    f"Could not acquire lock for creating deposit for user {user_id} (key: {lock_key})"
                )
                raise ValueError(
                    "Операция уже выполняется. Пожалуйста, подождите."
                )

            # R17-3: Check emergency stop (DB flag or static config flag)
            from app.repositories.global_settings_repository import (
                GlobalSettingsRepository,
            )

            settings_repo = GlobalSettingsRepository(self.session)
            global_settings = await settings_repo.get_settings()

            if (
                settings.emergency_stop_deposits
                or getattr(global_settings, "emergency_stop_deposits", False)
            ):
                logger.warning(
                    "Deposit blocked by emergency stop for user %s, level %s",
                    user_id,
                    level,
                )
                raise ValueError(
                    "⚠️ Временная приостановка депозитов из-за технических работ.\n\n"
                    "Депозиты будут доступны после восстановления.\n\n"
                    "Следите за обновлениями в нашем канале."
                )

            # R11-2: Check blockchain maintenance mode
            # If blockchain is down, create deposit with PENDING_NETWORK_RECOVERY status
            deposit_status = TransactionStatus.PENDING.value
            if settings.blockchain_maintenance_mode:
                deposit_status = TransactionStatus.PENDING_NETWORK_RECOVERY.value
                logger.info(
                    f"R11-2: Creating deposit with PENDING_NETWORK_RECOVERY status "
                    f"due to blockchain maintenance mode for user {user_id}, level {level}"
                )

            # R17-1, R17-2: Get current deposit level version
            from app.repositories.deposit_level_version_repository import (
                DepositLevelVersionRepository,
            )

            version_repo = DepositLevelVersionRepository(self.session)
            level_version = await version_repo.get_current_version(level)

            if not level_version:
                raise ValueError(
                    f"Level {level} is not available. "
                    "This level has been temporarily disabled."
                )

            # R17-2: Check if level is active
            if not level_version.is_active:
                raise ValueError(
                    f"Level {level} is temporarily unavailable. "
                    "Please try again later or contact support."
                )

            # R18-1: Dust attack protection - check minimum deposit amount
            min_deposit = Decimal(str(settings.minimum_deposit_amount))
            if amount < min_deposit:
                logger.warning(
                    f"Dust attack attempt blocked: user {user_id}, "
                    f"amount {amount} < minimum {min_deposit}"
                )
                raise ValueError(
                    f"Минимальная сумма депозита: {min_deposit} USDT. "
                    f"Попытка депозита {amount} USDT отклонена."
                )

            # Validate amount matches level version
            if amount < level_version.amount:
                raise ValueError(
                    f"Amount {amount} is less than required "
                    f"{level_version.amount} for level {level}"
                )

            # Validate level
            if not 1 <= level <= 5:
                raise ValueError("Level must be 1-5")

            # Validate amount
            if amount <= 0:
                raise ValueError("Amount must be positive")

            try:
                # R17-1: Calculate ROI cap from version (not settings)
                roi_cap_percent = Decimal(str(level_version.roi_cap_percent))
                roi_cap = amount * (roi_cap_percent / 100)

                deposit = await self.deposit_repo.create(
                    user_id=user_id,
                    level=level,
                    amount=amount,
                    tx_hash=tx_hash,
                    deposit_version_id=level_version.id,  # R17-1: Link to version
                    roi_cap_amount=roi_cap,
                    status=deposit_status,  # R11-2: PENDING or PENDING_NETWORK_RECOVERY
                )

                await self.session.commit()
                logger.info("Deposit created", extra={"deposit_id": deposit.id})

                return deposit

            except Exception as e:
                await self.session.rollback()
                logger.error(f"Failed to create deposit: {e}")
                raise

    async def confirm_deposit(
        self, deposit_id: int, block_number: int
    ) -> Deposit | None:
        """
        Confirm deposit after blockchain confirmation.

        Processes referral rewards automatically after confirmation.
        Sets next_accrual_at based on global settings.

        Args:
            deposit_id: Deposit ID
            block_number: Confirmation block number

        Returns:
            Updated deposit
        """
        from datetime import UTC, datetime, timedelta
        from app.repositories.global_settings_repository import GlobalSettingsRepository

        try:
            # R12-1: Calculate next_accrual_at based on settings
            settings_repo = GlobalSettingsRepository(self.session)
            global_settings = await settings_repo.get_settings()
            
            roi_settings = global_settings.roi_settings or {}
            accrual_period_hours = int(roi_settings.get("REWARD_ACCRUAL_PERIOD_HOURS", 6))
            
            # Start cycle immediately or after period?
            # "Установить next_accrual_at = datetime.now(UTC) ... чтобы запустить цикл"
            # Usually accrual happens after period. But if we want "immediate" effect for new users, 
            # we might set it to now + period. The previous fix set it to NOW because they were already waiting.
            # Standard logic: Accrue after X hours.
            now = datetime.now(UTC)
            next_accrual = now + timedelta(hours=accrual_period_hours)

            deposit = await self.deposit_repo.update(
                deposit_id,
                status=TransactionStatus.CONFIRMED.value,
                block_number=block_number,
                confirmed_at=now,
                next_accrual_at=next_accrual, # Set next accrual date
            )

            if deposit:
                await self.session.commit()
                logger.info(
                    "Deposit confirmed", extra={"deposit_id": deposit_id}
                )

                # Process referral rewards after deposit confirmation
                from app.services.referral_service import ReferralService

                referral_service = ReferralService(self.session)
                success, total_rewards, error = (
                    await referral_service.process_referral_rewards(
                        user_id=deposit.user_id, deposit_amount=deposit.amount
                    )
                )

                if success:
                    logger.info(
                        "Referral rewards processed",
                        extra={
                            "deposit_id": deposit_id,
                            "user_id": deposit.user_id,
                            "total_rewards": str(total_rewards),
                        },
                    )
                else:
                    logger.warning(
                        "Failed to process referral rewards",
                        extra={
                            "deposit_id": deposit_id,
                            "user_id": deposit.user_id,
                            "error": error,
                        },
                    )

            return deposit

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to confirm deposit: {e}")
            raise

    async def get_active_deposits(
        self, user_id: int
    ) -> list[Deposit]:
        """Get user's active deposits (ROI not completed)."""
        return await self.deposit_repo.get_active_deposits(user_id)

    async def get_level1_roi_progress(self, user_id: int) -> dict:
        """
        Get ROI progress for level 1 deposits.

        Args:
            user_id: User ID

        Returns:
            Dict with ROI progress information
        """
        # Get level 1 deposits
        deposits = await self.deposit_repo.find_by(
            user_id=user_id, level=1
        )

        if not deposits:
            return {
                "has_active_deposit": False,
                "is_completed": False,
                "deposit_amount": Decimal("0"),
                "roi_percent": 0.0,
                "roi_paid": Decimal("0"),
                "roi_remaining": Decimal("0"),
                "roi_cap": Decimal("0"),
            }

        # Get most recent deposit
        deposit = max(deposits, key=lambda d: d.created_at)

        # Calculate ROI progress
        roi_paid = getattr(deposit, "roi_paid_amount", Decimal("0"))
        roi_cap = deposit.roi_cap_amount
        roi_remaining = roi_cap - roi_paid
        roi_percent = float(roi_paid / roi_cap * 100) if roi_cap > 0 else 0.0
        is_completed = roi_paid >= roi_cap

        return {
            "has_active_deposit": True,
            "is_completed": is_completed,
            "deposit_amount": deposit.amount,
            "roi_percent": roi_percent,
            "roi_paid": roi_paid,
            "roi_remaining": roi_remaining,
            "roi_cap": roi_cap,
        }

    async def get_platform_stats(self) -> dict:
        """
        Get platform-wide deposit statistics.

        Returns:
            Dict with total deposits, amounts, and breakdown by level
        """
        # Get all confirmed deposits
        all_deposits = await self.deposit_repo.find_by(
            status=TransactionStatus.CONFIRMED.value
        )

        # Calculate totals
        total_deposits = len(all_deposits)
        total_amount = sum(d.amount for d in all_deposits)

        # Get unique users with deposits
        unique_users = len(set(d.user_id for d in all_deposits))

        # Count by level
        deposits_by_level = {}
        for level in [1, 2, 3, 4, 5]:
            level_deposits = [d for d in all_deposits if d.level == level]
            deposits_by_level[level] = len(level_deposits)

        return {
            "total_deposits": total_deposits,
            "total_amount": total_amount,
            "total_users": unique_users,
            "deposits_by_level": deposits_by_level,
        }

    async def get_detailed_stats(self) -> list[dict]:
        """
        Get detailed deposit statistics for admin.
        
        Returns:
            List of dicts with deposit details:
            - user_id, username
            - amount
            - roi_paid, roi_cap
            - next_accrual_at
            - status
        """
        from sqlalchemy import select
        from app.models.user import User

        # Join User to get username
        stmt = (
            select(Deposit, User)
            .join(User, Deposit.user_id == User.id)
            .where(
                Deposit.status == TransactionStatus.CONFIRMED.value,
                Deposit.is_roi_completed == False # Active deposits only
            )
            .order_by(Deposit.created_at.desc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        stats = []
        for deposit, user in rows:
            stats.append({
                "deposit_id": deposit.id,
                "user_id": user.id,
                "username": user.username or str(user.telegram_id),
                "amount": deposit.amount,
                "roi_paid": deposit.roi_paid_amount,
                "roi_cap": deposit.roi_cap_amount,
                "next_accrual_at": deposit.next_accrual_at,
                "level": deposit.level
            })
        
        return stats
