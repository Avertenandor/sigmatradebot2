"""
Global Settings repository.
"""

from decimal import Decimal

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
    ) -> GlobalSettings:
        """Update settings."""
        settings = await self.get_settings()

        if min_withdrawal_amount is not None:
            settings.min_withdrawal_amount = min_withdrawal_amount
        
        if daily_withdrawal_limit is not None:
            settings.daily_withdrawal_limit = daily_withdrawal_limit
            
        if is_daily_limit_enabled is not None:
            settings.is_daily_limit_enabled = is_daily_limit_enabled
            
        if auto_withdrawal_enabled is not None:
            settings.auto_withdrawal_enabled = auto_withdrawal_enabled

        await self.session.commit()
        await self.session.refresh(settings)
        return settings

