"""
UserAction repository.

Data access layer for UserAction model.
"""

from typing import List
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_action import UserAction
from app.repositories.base import BaseRepository


class UserActionRepository(BaseRepository[UserAction]):
    """UserAction repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize user action repository."""
        super().__init__(UserAction, session)

    async def get_by_user(
        self, user_id: int, action_type: Optional[str] = None
    ) -> List[UserAction]:
        """
        Get actions by user.

        Args:
            user_id: User ID
            action_type: Optional action type filter

        Returns:
            List of user actions
        """
        filters = {"user_id": user_id}
        if action_type:
            filters["action_type"] = action_type

        return await self.find_by(**filters)

    async def get_by_type(
        self, action_type: str
    ) -> List[UserAction]:
        """
        Get actions by type.

        Args:
            action_type: Action type

        Returns:
            List of actions
        """
        return await self.find_by(action_type=action_type)

    async def cleanup_old_actions(
        self, days: int = 7
    ) -> int:
        """
        Delete actions older than specified days.

        Args:
            days: Number of days (default: 7)

        Returns:
            Number of deleted actions
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        stmt = (
            select(UserAction)
            .where(UserAction.created_at < cutoff_date)
        )
        result = await self.session.execute(stmt)
        actions = list(result.scalars().all())

        for action in actions:
            await self.session.delete(action)

        await self.session.flush()
        return len(actions)
