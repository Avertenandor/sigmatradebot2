"""
AdminAction repository.

Data access layer for AdminAction model.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import desc, select, Numeric
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_action import AdminAction
from app.repositories.base import BaseRepository


class AdminActionRepository(BaseRepository[AdminAction]):
    """AdminAction repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize admin action repository."""
        super().__init__(AdminAction, session)

    async def update(
        self, id: int, **data: Any
    ) -> AdminAction | None:
        """
        Update admin action by ID.

        R18-4: Prevents updates to immutable actions.

        Args:
            id: Action ID
            **data: Updated data

        Returns:
            Updated action or None if not found/immutable

        Raises:
            ValueError: If action is immutable
        """
        entity = await self.get_by_id(id)
        if not entity:
            return None

        # R18-4: Check if immutable
        if entity.is_immutable:
            raise ValueError(
                f"AdminAction {id} is immutable and cannot be modified"
            )

        return await super().update(id, **data)

    async def delete(self, id: int) -> bool:
        """
        Delete admin action by ID.

        R18-4: Prevents deletion of immutable actions.

        Args:
            id: Action ID

        Returns:
            True if deleted, False if not found/immutable

        Raises:
            ValueError: If action is immutable
        """
        entity = await self.get_by_id(id)
        if not entity:
            return False

        # R18-4: Check if immutable
        if entity.is_immutable:
            raise ValueError(
                f"AdminAction {id} is immutable and cannot be deleted"
            )

        return await super().delete(id)

    async def get_by_admin_id(
        self,
        admin_id: int,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AdminAction]:
        """
        Get actions by admin ID.

        Args:
            admin_id: Admin ID
            limit: Max number of results
            offset: Number of results to skip

        Returns:
            List of admin actions
        """
        stmt = (
            select(AdminAction)
            .where(AdminAction.admin_id == admin_id)
            .order_by(desc(AdminAction.created_at))
        )

        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_admin_and_type(
        self,
        admin_id: int,
        action_type: str,
        since: datetime | None = None,
    ) -> int:
        """
        Count actions by admin and type since timestamp.

        R10-3: Used for detecting suspicious activity patterns.

        Args:
            admin_id: Admin ID
            action_type: Action type
            since: Count actions since this timestamp

        Returns:
            Count of matching actions
        """
        from sqlalchemy import func

        stmt = (
            select(func.count(AdminAction.id))
            .where(AdminAction.admin_id == admin_id)
            .where(AdminAction.action_type == action_type)
        )

        if since:
            stmt = stmt.where(AdminAction.created_at >= since)

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def sum_withdrawal_amounts_by_admin(
        self,
        admin_id: int,
        since: datetime | None = None,
    ) -> float:
        """
        R18-4: Sum withdrawal amounts approved by admin since timestamp.

        Args:
            admin_id: Admin ID
            since: Sum withdrawals since this timestamp

        Returns:
            Total withdrawal amount (USDT)
        """
        from sqlalchemy import func
        from sqlalchemy.dialects.postgresql import JSONB

        # Get all withdrawal actions and sum in Python
        # (PostgreSQL JSONB extraction is complex, so we do it in Python)
        stmt = (
            select(AdminAction)
            .where(AdminAction.admin_id == admin_id)
            .where(AdminAction.action_type == "WITHDRAWAL_APPROVED")
        )

        if since:
            stmt = stmt.where(AdminAction.created_at >= since)

        result = await self.session.execute(stmt)
        actions = list(result.scalars().all())

        total = 0.0
        for action in actions:
            if action.details and "amount" in action.details:
                try:
                    amount = float(action.details["amount"])
                    total += amount
                except (ValueError, TypeError):
                    pass

        return total

    async def get_recent(
        self,
        limit: int = 100,
        admin_id: int | None = None,
    ) -> list[AdminAction]:
        """
        Get recent admin actions.

        Args:
            limit: Max number of results (default: 100)
            admin_id: Optional admin ID filter

        Returns:
            List of recent admin actions
        """
        stmt = (
            select(AdminAction)
            .order_by(desc(AdminAction.created_at))
            .limit(limit)
        )

        if admin_id:
            stmt = stmt.where(AdminAction.admin_id == admin_id)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_action_type(
        self,
        action_type: str,
        limit: int | None = None,
    ) -> list[AdminAction]:
        """
        Get actions by type.

        Args:
            action_type: Action type string
            limit: Max number of results

        Returns:
            List of admin actions
        """
        stmt = (
            select(AdminAction)
            .where(AdminAction.action_type == action_type)
            .order_by(desc(AdminAction.created_at))
        )

        if limit:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_target_user(
        self,
        target_user_id: int,
        limit: int | None = None,
    ) -> list[AdminAction]:
        """
        Get actions targeting specific user.

        Args:
            target_user_id: Target user ID
            limit: Max number of results

        Returns:
            List of admin actions
        """
        stmt = (
            select(AdminAction)
            .where(AdminAction.target_user_id == target_user_id)
            .order_by(desc(AdminAction.created_at))
        )

        if limit:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

