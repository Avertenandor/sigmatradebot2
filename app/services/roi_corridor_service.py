"""
ROI Corridor Service.

Manages ROI corridor configurations and rate generation.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.deposit_corridor_history_repository import (
    DepositCorridorHistoryRepository,
)
from app.services.settings_service import SettingsService


class RoiCorridorService:
    """Service for managing ROI corridors and rate generation."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize ROI corridor service.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.settings = SettingsService(session)
        self.history_repo = DepositCorridorHistoryRepository(session)

    async def get_corridor_config(self, level: int) -> dict:
        """
        Get current corridor configuration for a level.

        Args:
            level: Deposit level (1-5)

        Returns:
            Dictionary with corridor configuration
        """
        mode = await self.settings.get(
            f"LEVEL_{level}_ROI_MODE", default="custom"
        )
        roi_min = Decimal(
            await self.settings.get(f"LEVEL_{level}_ROI_MIN", default="0.8")
        )
        roi_max = Decimal(
            await self.settings.get(f"LEVEL_{level}_ROI_MAX", default="10.0")
        )
        roi_fixed = Decimal(
            await self.settings.get(f"LEVEL_{level}_ROI_FIXED", default="5.0")
        )

        return {
            "mode": mode,
            "roi_min": roi_min,
            "roi_max": roi_max,
            "roi_fixed": roi_fixed,
        }

    async def set_corridor(
        self,
        level: int,
        mode: str,
        roi_min: Decimal | None,
        roi_max: Decimal | None,
        roi_fixed: Decimal | None,
        admin_id: int,
        applies_to: str,
        reason: str | None = None,
    ) -> tuple[bool, str | None]:
        """
        Set corridor configuration for a level.

        Args:
            level: Deposit level (1-5)
            mode: Mode ('custom' or 'equal')
            roi_min: Minimum ROI percentage (for custom mode)
            roi_max: Maximum ROI percentage (for custom mode)
            roi_fixed: Fixed ROI percentage (for equal mode)
            admin_id: Admin who is making the change
            applies_to: Application scope ('current' or 'next')

        Returns:
            Tuple of (success, error_message)
        """
        # Validation
        if mode == "custom":
            if roi_min is None or roi_max is None:
                return False, "Для режима Custom требуются min и max"
            if roi_min >= roi_max:
                return False, "Минимум должен быть меньше максимума"
            if roi_min < 0 or roi_max < 0:
                return False, "Проценты не могут быть отрицательными"
        elif mode == "equal":
            if roi_fixed is None:
                return False, "Для режима Поровну требуется фиксированный процент"
            if roi_fixed < 0:
                return False, "Процент не может быть отрицательным"
        else:
            return False, f"Неизвестный режим: {mode}"

        # Save to history
        await self.history_repo.create(
            level=level,
            mode=mode,
            roi_min=roi_min,
            roi_max=roi_max,
            roi_fixed=roi_fixed,
            changed_by_admin_id=admin_id,
            applies_to=applies_to,
            reason=reason,
        )

        # Apply settings
        if applies_to == "current":
            await self.settings.set(f"LEVEL_{level}_ROI_MODE", mode)
            if mode == "custom":
                await self.settings.set(
                    f"LEVEL_{level}_ROI_MIN", str(roi_min)
                )
                await self.settings.set(
                    f"LEVEL_{level}_ROI_MAX", str(roi_max)
                )
            else:
                await self.settings.set(
                    f"LEVEL_{level}_ROI_FIXED", str(roi_fixed)
                )
        else:
            # Store for next session
            await self.settings.set(f"LEVEL_{level}_ROI_MODE_NEXT", mode)
            if mode == "custom":
                await self.settings.set(
                    f"LEVEL_{level}_ROI_MIN_NEXT", str(roi_min)
                )
                await self.settings.set(
                    f"LEVEL_{level}_ROI_MAX_NEXT", str(roi_max)
                )
            else:
                await self.settings.set(
                    f"LEVEL_{level}_ROI_FIXED_NEXT", str(roi_fixed)
                )

        await self.session.commit()

        logger.info(
            "Corridor set for level",
            extra={
                "level": level,
                "mode": mode,
                "applies_to": applies_to,
                "admin_id": admin_id,
            },
        )

        return True, None

    def generate_rate_from_corridor(
        self, roi_min: Decimal, roi_max: Decimal
    ) -> Decimal:
        """
        Generate random rate from corridor with bias to lower values.

        Uses weighted distribution:
        - 60% chance: lower third of corridor
        - 30% chance: middle third of corridor
        - 10% chance: upper third of corridor

        Args:
            roi_min: Minimum ROI percentage
            roi_max: Maximum ROI percentage

        Returns:
            Generated rate as Decimal
        """
        rand = random.random()
        range_size = roi_max - roi_min

        if rand < 0.6:  # 60% - lower third
            rate = roi_min + (
                range_size * Decimal(str(random.random() * 0.33))
            )
        elif rand < 0.9:  # 30% - middle third
            rate = roi_min + (
                range_size * Decimal(str(0.33 + random.random() * 0.34))
            )
        else:  # 10% - upper third
            rate = roi_min + (
                range_size * Decimal(str(0.67 + random.random() * 0.33))
            )

        return rate.quantize(Decimal("0.01"))

    async def calculate_next_accrual_time(
        self, deposit_created_at: datetime
    ) -> datetime:
        """
        Calculate next accrual time based on period setting.

        Args:
            deposit_created_at: When the deposit was created

        Returns:
            Next accrual timestamp
        """
        period_hours = int(
            await self.settings.get(
                "REWARD_ACCRUAL_PERIOD_HOURS", default="6"
            )
        )
        return deposit_created_at + timedelta(hours=period_hours)

    async def apply_next_session_settings(self) -> None:
        """
        Apply 'next' session settings to 'current'.

        This is called when transitioning to a new accrual cycle.
        """
        for level in range(1, 6):
            mode_next = await self.settings.get(f"LEVEL_{level}_ROI_MODE_NEXT")
            if mode_next:
                await self.settings.set(f"LEVEL_{level}_ROI_MODE", mode_next)

                if mode_next == "custom":
                    min_next = await self.settings.get(
                        f"LEVEL_{level}_ROI_MIN_NEXT"
                    )
                    max_next = await self.settings.get(
                        f"LEVEL_{level}_ROI_MAX_NEXT"
                    )
                    if min_next:
                        await self.settings.set(
                            f"LEVEL_{level}_ROI_MIN", min_next
                        )
                    if max_next:
                        await self.settings.set(
                            f"LEVEL_{level}_ROI_MAX", max_next
                        )
                else:
                    fixed_next = await self.settings.get(
                        f"LEVEL_{level}_ROI_FIXED_NEXT"
                    )
                    if fixed_next:
                        await self.settings.set(
                            f"LEVEL_{level}_ROI_FIXED", fixed_next
                        )

                # Clear 'next' settings
                await self.settings.delete(f"LEVEL_{level}_ROI_MODE_NEXT")
                await self.settings.delete(f"LEVEL_{level}_ROI_MIN_NEXT")
                await self.settings.delete(f"LEVEL_{level}_ROI_MAX_NEXT")
                await self.settings.delete(f"LEVEL_{level}_ROI_FIXED_NEXT")

                logger.info(
                    "Applied next session settings",
                    extra={"level": level, "mode": mode_next},
                )

        await self.session.commit()

    async def get_accrual_period_hours(self) -> int:
        """
        Get current accrual period in hours.

        Returns:
            Period in hours
        """
        return int(
            await self.settings.get(
                "REWARD_ACCRUAL_PERIOD_HOURS", default="6"
            )
        )

    async def set_accrual_period_hours(
        self, hours: int, admin_id: int
    ) -> tuple[bool, str | None]:
        """
        Set accrual period in hours.

        Args:
            hours: Period in hours (1-24)
            admin_id: Admin making the change

        Returns:
            Tuple of (success, error_message)
        """
        if hours < 1 or hours > 24:
            return False, "Период должен быть от 1 до 24 часов"

        await self.settings.set("REWARD_ACCRUAL_PERIOD_HOURS", str(hours))
        await self.session.commit()

        logger.info(
            "Accrual period changed",
            extra={"hours": hours, "admin_id": admin_id},
        )

        return True, None

    async def set_level_amount(
        self,
        level: int,
        amount: Decimal,
        admin_id: int,
    ) -> tuple[bool, str | None]:
        """
        Set deposit amount for a level (creates new version).

        Args:
            level: Deposit level (1-5)
            amount: New amount in USDT
            admin_id: Admin who is making the change

        Returns:
            Tuple of (success, error_message)
        """
        if amount <= 0:
            return False, "Сумма должна быть положительной"

        # Get current configuration to preserve settings
        config = await self.get_corridor_config(level)
        
        # Create new version with updated amount but same ROI settings
        from app.repositories.deposit_level_version_repository import (
            DepositLevelVersionRepository,
        )
        version_repo = DepositLevelVersionRepository(self.session)
        
        await version_repo.create(
            level=level,
            amount=amount,
            roi_mode=config["mode"],
            roi_min=config["roi_min"],
            roi_max=config["roi_max"],
            roi_fixed=config["roi_fixed"],
            created_by_id=admin_id,
        )
        
        await self.session.commit()

        logger.info(
            "Level amount updated",
            extra={
                "level": level,
                "amount": float(amount),
                "admin_id": admin_id,
            },
        )

        return True, None

    async def validate_corridor_settings(
        self, roi_min: Decimal | None, roi_max: Decimal | None
    ) -> tuple[bool, str | None]:
        """
        Validate corridor settings and return warnings.

        Args:
            roi_min: Minimum ROI percentage
            roi_max: Maximum ROI percentage

        Returns:
            Tuple of (needs_confirmation, warning_message)
        """
        if roi_min is None or roi_max is None:
            return False, None

        warnings = []

        if roi_min < Decimal("0.5"):
            warnings.append(
                f"⚠️ Очень низкий минимум: {roi_min}% (рекомендуется >= 0.5%)"
            )

        if roi_max > Decimal("20"):
            warnings.append(
                f"⚠️ Очень высокий максимум: {roi_max}% (рекомендуется <= 20%)"
            )

        if roi_max - roi_min < Decimal("1"):
            warnings.append(
                f"⚠️ Узкий коридор: {roi_max - roi_min}% "
                "(рекомендуется >= 1%)"
            )

        if warnings:
            return True, "\n".join(warnings)

        return False, None

