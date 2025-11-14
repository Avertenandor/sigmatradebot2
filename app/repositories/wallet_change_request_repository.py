"""
WalletChangeRequest repository.

Data access layer for WalletChangeRequest model.
"""

from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet_change_request import (
    WalletChangeRequest,
)
from app.repositories.base import BaseRepository


class WalletChangeRequestRepository(
    BaseRepository[WalletChangeRequest]
):
    """WalletChangeRequest repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize wallet change request repository."""
        super().__init__(WalletChangeRequest, session)

    async def get_by_status(
        self, status: str
    ) -> List[WalletChangeRequest]:
        """
        Get requests by status.

        Args:
            status: Request status

        Returns:
            List of requests
        """
        return await self.find_by(status=status)

    async def get_by_type(
        self, type: str
    ) -> List[WalletChangeRequest]:
        """
        Get requests by type.

        Args:
            type: Request type

        Returns:
            List of requests
        """
        return await self.find_by(type=type)

    async def get_pending_requests(
        self,
    ) -> List[WalletChangeRequest]:
        """
        Get all pending requests.

        Returns:
            List of pending requests
        """
        return await self.get_by_status("pending")

    async def get_active_requests(
        self,
    ) -> List[WalletChangeRequest]:
        """
        Get active (pending or approved) requests.

        Returns:
            List of active requests
        """
        pending = await self.get_by_status("pending")
        approved = await self.get_by_status("approved")
        return pending + approved
