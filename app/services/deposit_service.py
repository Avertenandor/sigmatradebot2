"""
Deposit service.

Business logic for deposit management and ROI tracking.
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

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
        tx_hash: Optional[str] = None,
    ) -> Deposit:
        """
        Create new deposit.

        Args:
            user_id: User ID
            level: Deposit level (1-5)
            amount: Deposit amount
            tx_hash: Blockchain transaction hash

        Returns:
            Created deposit
        """
        # Validate level
        if not 1 <= level <= 5:
            raise ValueError("Level must be 1-5")

        # Calculate ROI cap (500% for level 1, varies by level)
        roi_multiplier = Decimal("5.0")  # 500%
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
        logger.info(f"Deposit created", extra={"deposit_id": deposit.id})

        return deposit

    async def confirm_deposit(
        self, deposit_id: int, block_number: int
    ) -> Optional[Deposit]:
        """
        Confirm deposit after blockchain confirmation.

        Args:
            deposit_id: Deposit ID
            block_number: Confirmation block number

        Returns:
            Updated deposit
        """
        deposit = await self.deposit_repo.update(
            deposit_id,
            status=TransactionStatus.CONFIRMED.value,
            block_number=block_number,
        )

        if deposit:
            await self.session.commit()
            logger.info(f"Deposit confirmed", extra={"deposit_id": deposit_id})

        return deposit

    async def get_active_deposits(
        self, user_id: int
    ) -> list[Deposit]:
        """Get user's active deposits (ROI not completed)."""
        return await self.deposit_repo.get_active_deposits(user_id)
