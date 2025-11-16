"""
Deposit service.

Business logic for deposit management and ROI tracking.
"""

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
    ) -> Deposit:
        """
        Create new deposit with proper error handling.

        Args:
            user_id: User ID
            level: Deposit level (1-5)
            amount: Deposit amount
            tx_hash: Blockchain transaction hash

        Returns:
            Created deposit

        Raises:
            ValueError: If level or amount is invalid
        """
        # Validate level
        if not 1 <= level <= 5:
            raise ValueError("Level must be 1-5")

        # Validate amount
        if amount <= 0:
            raise ValueError("Amount must be positive")

        try:
            # Calculate ROI cap from settings
            roi_multiplier = Decimal(str(settings.roi_cap_multiplier))
            roi_cap = amount * roi_multiplier

            deposit = await self.deposit_repo.create(
                user_id=user_id,
                level=level,
                amount=amount,
                tx_hash=tx_hash,
                roi_cap_amount=roi_cap,
                status=TransactionStatus.PENDING.value,
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

        Args:
            deposit_id: Deposit ID
            block_number: Confirmation block number

        Returns:
            Updated deposit
        """
        try:
            deposit = await self.deposit_repo.update(
                deposit_id,
                status=TransactionStatus.CONFIRMED.value,
                block_number=block_number,
            )

            if deposit:
                await self.session.commit()
                logger.info(
                    "Deposit confirmed", extra={"deposit_id": deposit_id}
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
