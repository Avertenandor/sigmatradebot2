"""
AdminSession repository.

Data access layer for AdminSession model.
"""

from typing import List, Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_session import AdminSession
from app.repositories.base import BaseRepository


class AdminSessionRepository(BaseRepository[AdminSession]):
    """AdminSession repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize admin session repository."""
        super().__init__(AdminSession, session)

    async def get_by_token(
        self, session_token: str
    ) -> Optional[AdminSession]:
        """
        Get session by token.

        Args:
            session_token: Session token

        Returns:
            AdminSession or None
        """
        return await self.get_by(session_token=session_token)

    async def get_active_sessions(
        self, admin_id: int
    ) -> List[AdminSession]:
        """
        Get active sessions for admin.

        Args:
            admin_id: Admin ID

        Returns:
            List of active sessions
        """
        return await self.find_by(
            admin_id=admin_id, is_active=True
        )

    async def deactivate_all_sessions(
        self, admin_id: int
    ) -> int:
        """
        Deactivate all sessions for admin.

        Args:
            admin_id: Admin ID

        Returns:
            Number of deactivated sessions
        """
        sessions = await self.get_active_sessions(admin_id)

        for session in sessions:
            session.is_active = False

        await self.session.flush()
        return len(sessions)

    async def cleanup_expired_sessions(self) -> int:
        """
        Cleanup expired sessions.

        Returns:
            Number of cleaned up sessions
        """
        now = datetime.now()

        stmt = (
            select(AdminSession)
            .where(AdminSession.is_active == True)
            .where(AdminSession.expires_at < now)
        )
        result = await self.session.execute(stmt)
        sessions = list(result.scalars().all())

        for session in sessions:
            session.is_active = False

        await self.session.flush()
        return len(sessions)
