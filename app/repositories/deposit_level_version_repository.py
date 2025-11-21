"""
Deposit level version repository.

R17-1, R17-2: Data access layer for DepositLevelVersion model.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deposit_level_version import DepositLevelVersion
from app.repositories.base import BaseRepository


class DepositLevelVersionRepository(
    BaseRepository[DepositLevelVersion]
):
    """Deposit level version repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize deposit level version repository."""
        super().__init__(DepositLevelVersion, session)

    async def get_current_version(
        self, level_number: int
    ) -> DepositLevelVersion | None:
        """
        Get current active version for level.

        R17-1: Returns the latest active version.

        Args:
            level_number: Level number (1-5)

        Returns:
            Current version or None
        """
        now = datetime.now(UTC)

        stmt = (
            select(DepositLevelVersion)
            .where(DepositLevelVersion.level_number == level_number)
            .where(DepositLevelVersion.is_active == True)  # noqa: E712
            .where(
                (DepositLevelVersion.effective_until.is_(None))
                | (DepositLevelVersion.effective_until > now)
            )
            .where(DepositLevelVersion.effective_from <= now)
            .order_by(DepositLevelVersion.version.desc())
            .limit(1)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active_levels(self) -> list[DepositLevelVersion]:
        """
        Get all active levels (current versions).

        R17-2: Returns all levels that are currently available.

        Returns:
            List of active deposit level versions
        """
        now = datetime.now(UTC)

        stmt = (
            select(DepositLevelVersion)
            .where(DepositLevelVersion.is_active == True)  # noqa: E712
            .where(
                (DepositLevelVersion.effective_until.is_(None))
                | (DepositLevelVersion.effective_until > now)
            )
            .where(DepositLevelVersion.effective_from <= now)
            .order_by(DepositLevelVersion.level_number.asc())
        )

        # Get latest version for each level
        result = await self.session.execute(stmt)
        versions = list(result.scalars().all())

        # Group by level and take latest version
        level_map: dict[int, DepositLevelVersion] = {}
        for version in versions:
            if (
                version.level_number not in level_map
                or version.version > level_map[version.level_number].version
            ):
                level_map[version.level_number] = version

        return list(level_map.values())

    async def is_level_available(self, level_number: int) -> bool:
        """
        Check if level is currently available.

        R17-2: Checks if level is active and not expired.

        Args:
            level_number: Level number

        Returns:
            True if level is available
        """
        current = await self.get_current_version(level_number)
        return current is not None

