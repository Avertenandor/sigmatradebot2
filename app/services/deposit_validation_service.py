"""
Deposit validation service.

Validates deposit purchase eligibility based on:
1. Strict order (must buy levels sequentially)
2. Partner requirements (must have active partners for higher levels)
"""

from decimal import Decimal

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TransactionStatus
from app.repositories.deposit_level_version_repository import (
    DepositLevelVersionRepository,
)
from app.repositories.deposit_repository import DepositRepository
from app.repositories.referral_repository import ReferralRepository
from app.services.referral_service import ReferralService

# Deposit levels configuration (from TZ)
DEPOSIT_LEVELS = {
    1: Decimal("10"),   # 10 USDT
    2: Decimal("50"),   # 50 USDT
    3: Decimal("100"),  # 100 USDT
    4: Decimal("150"),  # 150 USDT
    5: Decimal("300"),  # 300 USDT
}

# Partner requirements for each level
# DISABLED: No partner requirements anymore
# Levels are controlled via is_active flag in DepositLevelVersion
PARTNER_REQUIREMENTS = {
    1: 0,  # No partners required
    2: 0,  # No partners required (was 1)
    3: 0,  # No partners required (was 1)
    4: 0,  # No partners required (was 1)
    5: 0,  # No partners required (was 1)
}


class DepositValidationService:
    """Service for validating deposit purchase eligibility."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize deposit validation service."""
        self.session = session
        self.deposit_repo = DepositRepository(session)
        self.referral_repo = ReferralRepository(session)
        self.referral_service = ReferralService(session)
        self.version_repo = DepositLevelVersionRepository(session)

    async def can_purchase_level(
        self, user_id: int, level: int
    ) -> tuple[bool, str | None]:
        """
        Check if user can purchase a specific deposit level.

        Args:
            user_id: User ID
            level: Deposit level (1-5)

        Returns:
            Tuple of (can_purchase, error_message)
        """
        # Validate level
        if level not in DEPOSIT_LEVELS:
            return False, f"Неверный уровень депозита: {level}"

        # Check 0: Level must be active (R17-2)
        level_version = await self.version_repo.get_current_version(level)
        if level_version and not level_version.is_active:
            return (
                False,
                f"Уровень {level} временно недоступен для покупки.",
            )

        # Check 1: Strict order - must have all previous levels
        if level > 1:
            has_previous = await self._has_all_previous_levels(user_id, level)
            if not has_previous:
                prev_level = level - 1
                return (
                    False,
                    f"Для покупки уровня {level} необходимо сначала "
                    f"купить уровень {prev_level}.\n\n"
                    f"Порядок покупки строгий: 1 → 2 → 3 → 4 → 5",
                )

        # Check 2: Partner requirements (for levels 2+)
        if level > 1:
            has_partners = await self._has_required_partners(user_id, level)
            if not has_partners:
                required = PARTNER_REQUIREMENTS[level]
                return (
                    False,
                    f"Для покупки уровня {level} необходимо минимум "
                    f"{required} активный партнер уровня L1 с "
                    f"активным депозитом.",
                )

        return True, None

    async def _has_all_previous_levels(
        self, user_id: int, target_level: int
    ) -> bool:
        """
        Check if user has all previous deposit levels.

        Args:
            user_id: User ID
            target_level: Target level to check

        Returns:
            True if all previous levels exist and are confirmed
        """
        # Get all confirmed deposits
        deposits = await self.deposit_repo.find_by(
            user_id=user_id,
            status=TransactionStatus.CONFIRMED.value,
        )

        # Get unique levels that user has
        user_levels = set(d.level for d in deposits)

        # Check if user has all levels from 1 to (target_level - 1)
        for level in range(1, target_level):
            if level not in user_levels:
                logger.debug(
                    "Missing previous level",
                    extra={
                        "user_id": user_id,
                        "target_level": target_level,
                        "missing_level": level,
                        "user_levels": list(user_levels),
                    },
                )
                return False

        return True

    async def _has_required_partners(
        self, user_id: int, level: int
    ) -> bool:
        """
        Check if user has required active partners.

        Args:
            user_id: User ID
            level: Deposit level

        Returns:
            True if user has required active partners
        """
        required = PARTNER_REQUIREMENTS.get(level, 0)
        if required == 0:
            return True  # No partners required

        # Get level 1 referrals (direct partners)
        l1_referrals = await self.referral_repo.get_by_referrer(
            referrer_id=user_id, level=1
        )

        if len(l1_referrals) < required:
            logger.debug(
                "Insufficient partners",
                extra={
                    "user_id": user_id,
                    "level": level,
                    "required": required,
                    "actual": len(l1_referrals),
                },
            )
            return False

        # Check if partners have active deposits
        active_partners = 0
        for referral in l1_referrals:
            partner_id = referral.referral_id
            # Check if partner has at least one confirmed deposit
            partner_deposits = await self.deposit_repo.find_by(
                user_id=partner_id,
                status=TransactionStatus.CONFIRMED.value,
            )
            if partner_deposits:
                active_partners += 1

        has_required = active_partners >= required

        logger.debug(
            "Partner check result",
            extra={
                "user_id": user_id,
                "level": level,
                "required": required,
                "active_partners": active_partners,
                "has_required": has_required,
            },
        )

        return has_required

    async def get_available_levels(self, user_id: int) -> dict:
        """
        Get available deposit levels for user with statuses.

        Args:
            user_id: User ID

        Returns:
            Dict with level statuses: available, unavailable, active
        """
        # Get user's confirmed deposits
        deposits = await self.deposit_repo.find_by(
            user_id=user_id,
            status=TransactionStatus.CONFIRMED.value,
        )
        user_levels = set(d.level for d in deposits)

        levels_status = {}

        for level in [1, 2, 3, 4, 5]:
            amount = DEPOSIT_LEVELS[level]
            can_purchase, error = await self.can_purchase_level(user_id, level)
            has_level = level in user_levels

            if has_level:
                status = "active"
                status_text = "Активен"
            elif can_purchase:
                status = "available"
                status_text = "Доступен к покупке"
            else:
                status = "unavailable"
                status_text = "Не доступен"

            levels_status[level] = {
                "level": level,
                "amount": amount,
                "status": status,
                "status_text": status_text,
                "error": error if not can_purchase else None,
            }

        return levels_status
