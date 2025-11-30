"""
Global Settings repository.
"""

from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.global_settings import GlobalSettings


class GlobalSettingsRepository:
    """Repository for GlobalSettings."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        self.session = session

    async def get_settings(self) -> GlobalSettings:
        """
        Get global settings (singleton).
        Creates default if not exists.
        """
        stmt = select(GlobalSettings).limit(1)
        result = await self.session.execute(stmt)
        settings = result.scalar_one_or_none()

        if not settings:
            logger.info("Initializing default global settings")
            settings = GlobalSettings(
                min_withdrawal_amount=Decimal("0.05"),
                is_daily_limit_enabled=False,
                auto_withdrawal_enabled=True,
                active_rpc_provider="quicknode",
                is_auto_switch_enabled=True,
                max_open_deposit_level=5,
                roi_settings={},
                emergency_stop_withdrawals=False,
                emergency_stop_deposits=False,
                emergency_stop_roi=False,
            )
            self.session.add(settings)
            await self.session.commit()
            await self.session.refresh(settings)

        return settings

    async def update_settings(
        self,
        min_withdrawal_amount: Decimal | None = None,
        daily_withdrawal_limit: Decimal | None = None,
        is_daily_limit_enabled: bool | None = None,
        auto_withdrawal_enabled: bool | None = None,
        active_rpc_provider: str | None = None,
        is_auto_switch_enabled: bool | None = None,
        max_open_deposit_level: int | None = None,
        roi_settings: dict[str, Any] | None = None,
        emergency_stop_withdrawals: bool | None = None,
        emergency_stop_deposits: bool | None = None,
        emergency_stop_roi: bool | None = None,
    ) -> GlobalSettings:
        """
        Update global settings.
        """
        settings = await self.get_settings()

        if min_withdrawal_amount is not None:
            settings.min_withdrawal_amount = min_withdrawal_amount
        if daily_withdrawal_limit is not None:
            settings.daily_withdrawal_limit = daily_withdrawal_limit
        if is_daily_limit_enabled is not None:
            settings.is_daily_limit_enabled = is_daily_limit_enabled
        if auto_withdrawal_enabled is not None:
            settings.auto_withdrawal_enabled = auto_withdrawal_enabled
        if active_rpc_provider is not None:
            settings.active_rpc_provider = active_rpc_provider
        if is_auto_switch_enabled is not None:
            settings.is_auto_switch_enabled = is_auto_switch_enabled
        if max_open_deposit_level is not None:
            settings.max_open_deposit_level = max_open_deposit_level
        if roi_settings is not None:
            # Merge or replace? For safety, we'll update the dict
            # Use existing if None passed? No, None check is above.
            # If we want partial updates to JSON, we need to fetch, update, set.
            # Here we assume full replacement or caller handles merging if they pass a dict.
            # Actually, merging is safer for concurrent updates, but let's replace for now as it's simpler.
            # Ideally we should merge:
            current = dict(settings.roi_settings)
            current.update(roi_settings)
            settings.roi_settings = current
        if emergency_stop_withdrawals is not None:
            settings.emergency_stop_withdrawals = emergency_stop_withdrawals
        if emergency_stop_deposits is not None:
            settings.emergency_stop_deposits = emergency_stop_deposits
        if emergency_stop_roi is not None:
            settings.emergency_stop_roi = emergency_stop_roi

        await self.session.commit()
        await self.session.refresh(settings)
        return settings
