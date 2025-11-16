"""
Wallet admin service.

Service for managing wallet change requests and approvals.
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet_change_request import WalletChangeRequest
from app.models.enums import WalletChangeStatus
from app.repositories.wallet_change_request_repository import (
    WalletChangeRequestRepository,
)


class WalletAdminService:
    """Service for wallet administration."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize wallet admin service."""
        self.session = session
        self.repository = WalletChangeRequestRepository(session)

    async def get_pending_requests(self) -> List[WalletChangeRequest]:
        """
        Get all pending wallet change requests.

        Returns:
            List of pending requests
        """
        return await self.repository.get_pending_requests()

    async def approve_request(
        self,
        request_id: int,
        admin_id: int,
        admin_notes: Optional[str] = None,
    ) -> WalletChangeRequest:
        """
        Approve a wallet change request.

        Args:
            request_id: Request ID to approve
            admin_id: Admin ID who is approving
            admin_notes: Optional admin notes

        Returns:
            Approved request

        Raises:
            ValueError: If request not found or cannot be approved
        """
        request = await self.repository.get_by_id(request_id)

        if not request:
            raise ValueError(f"Request {request_id} not found")

        if request.status != WalletChangeStatus.PENDING.value:
            raise ValueError(
                f"Request {request_id} is not pending "
                f"(status: {request.status})"
            )

        # Update request
        await self.repository.update(
            request.id,
            status=WalletChangeStatus.APPROVED.value,
            approved_by_admin_id=admin_id,
            approved_at=datetime.now(timezone.utc),
        )

        return request

    async def reject_request(
        self,
        request_id: int,
        admin_id: int,
        admin_notes: Optional[str] = None,
    ) -> WalletChangeRequest:
        """
        Reject a wallet change request.

        Args:
            request_id: Request ID to reject
            admin_id: Admin ID who is rejecting
            admin_notes: Optional admin notes
                (stored in reason field if provided)

        Returns:
            Rejected request

        Raises:
            ValueError: If request not found or cannot be rejected
        """
        request = await self.repository.get_by_id(request_id)

        if not request:
            raise ValueError(f"Request {request_id} not found")

        if request.status not in (
            WalletChangeStatus.PENDING.value,
            WalletChangeStatus.APPROVED.value,
        ):
            raise ValueError(
                f"Request {request_id} cannot be rejected "
                f"(status: {request.status})"
            )

        # Update request
        update_data = {
            "status": WalletChangeStatus.REJECTED.value,
            "approved_by_admin_id": admin_id,
            "approved_at": datetime.now(timezone.utc),
        }

        # Update reason if admin notes provided
        if admin_notes:
            if request.reason:
                update_data["reason"] = (
                    f"{request.reason}\n\nRejection notes: {admin_notes}"
                )
            else:
                update_data["reason"] = f"Rejection notes: {admin_notes}"

        # Save changes
        await self.repository.update(request.id, **update_data)

        return request
