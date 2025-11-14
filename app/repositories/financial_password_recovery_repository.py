"""
FinancialPasswordRecovery repository.

Data access layer for FinancialPasswordRecovery model.
"""

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_password_recovery import (
    FinancialPasswordRecovery,
)
from app.repositories.base import BaseRepository


class FinancialPasswordRecoveryRepository(
    BaseRepository[FinancialPasswordRecovery]
):
    """FinancialPasswordRecovery repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(FinancialPasswordRecovery, session)

    async def get_by_user(
        self, user_id: int, status: Optional[str] = None
    ) -> List[FinancialPasswordRecovery]:
        """
        Get recovery requests by user.

        Args:
            user_id: User ID
            status: Optional status filter

        Returns:
            List of recovery requests
        """
        filters = {"user_id": user_id}
        if status:
            filters["status"] = status

        return await self.find_by(**filters)

    async def get_pending_requests(
        self,
    ) -> List[FinancialPasswordRecovery]:
        """
        Get all pending recovery requests.

        Returns:
            List of pending requests
        """
        return await self.find_by(status="pending")

    async def has_active_request(
        self, user_id: int
    ) -> bool:
        """
        Check if user has active recovery request.

        Args:
            user_id: User ID

        Returns:
            True if has active request
        """
        return await self.exists(
            user_id=user_id,
            status="pending",
        )
