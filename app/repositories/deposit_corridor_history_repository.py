"""
Deposit corridor history repository.

Handles database operations for corridor history tracking.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deposit_corridor_history import DepositCorridorHistory


class DepositCorridorHistoryRepository:
    """Repository for deposit corridor history operations."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create(
        self,
        level: int,
        mode: str,
        roi_min: Decimal | None,
        roi_max: Decimal | None,
        roi_fixed: Decimal | None,
        changed_by_admin_id: int,
        applies_to: str,
        reason: str | None = None,
    ) -> DepositCorridorHistory:
        """
        Create corridor history record.

        Args:
            level: Deposit level (1-5)
            mode: Mode ('custom' or 'equal')
            roi_min: Minimum ROI percentage (for custom mode)
            roi_max: Maximum ROI percentage (for custom mode)
            roi_fixed: Fixed ROI percentage (for equal mode)
            changed_by_admin_id: Admin who made the change
            applies_to: Application scope ('current' or 'next')

        Returns:
            Created history record
        """
        history = DepositCorridorHistory(
            level=level,
            mode=mode,
            roi_min=roi_min,
            roi_max=roi_max,
            roi_fixed=roi_fixed,
            changed_by_admin_id=changed_by_admin_id,
            applies_to=applies_to,
            reason=reason,
        )
        self.session.add(history)
        await self.session.flush()
        return history

    async def get_history_for_level(
        self, level: int, limit: int = 100
    ) -> list[DepositCorridorHistory]:
        """
        Get corridor change history for a specific level.

        Args:
            level: Deposit level (1-5)
            limit: Maximum number of records to return

        Returns:
            List of history records, newest first
        """
        stmt = (
            select(DepositCorridorHistory)
            .where(DepositCorridorHistory.level == level)
            .order_by(DepositCorridorHistory.changed_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_history(
        self, limit: int = 100
    ) -> list[DepositCorridorHistory]:
        """
        Get corridor change history for all levels.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of history records, newest first
        """
        stmt = (
            select(DepositCorridorHistory)
            .order_by(DepositCorridorHistory.changed_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_for_level(
        self, level: int
    ) -> DepositCorridorHistory | None:
        """
        Get the most recent corridor change for a level.

        Args:
            level: Deposit level (1-5)

        Returns:
            Latest history record or None
        """
        stmt = (
            select(DepositCorridorHistory)
            .where(DepositCorridorHistory.level == level)
            .order_by(DepositCorridorHistory.changed_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

