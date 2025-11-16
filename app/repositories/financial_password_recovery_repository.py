"""
FinancialPasswordRecovery repository.

Data access layer for FinancialPasswordRecovery model.
"""


from sqlalchemy import select
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
        self, user_id: int, status: str | None = None
    ) -> list[FinancialPasswordRecovery]:
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
    ) -> list[FinancialPasswordRecovery]:
        """
        Get all pending recovery requests.

        Returns:
            List of pending requests
        """
        stmt = (
            select(FinancialPasswordRecovery)
            .where(FinancialPasswordRecovery.status == "pending")
            .order_by(FinancialPasswordRecovery.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

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
