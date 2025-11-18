"""
AdminAction repository.

Data access layer for AdminAction model.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_action import AdminAction
from app.repositories.base import BaseRepository


class AdminActionRepository(BaseRepository[AdminAction]):
    """AdminAction repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize admin action repository."""
        super().__init__(AdminAction, session)

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

