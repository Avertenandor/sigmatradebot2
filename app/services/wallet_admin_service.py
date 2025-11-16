"""
Wallet admin service.

Service for managing wallet change requests and approvals.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WalletChangeStatus
from app.models.wallet_change_request import WalletChangeRequest
from app.repositories.wallet_change_request_repository import (
    WalletChangeRequestRepository,
)


class WalletAdminService:
    """Service for wallet administration."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize wallet admin service."""
        self.session = session
        self.repository = WalletChangeRequestRepository(session)

    async def get_pending_requests(self) -> list[WalletChangeRequest]:
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
        admin_notes: str | None = None,
    ) -> WalletChangeRequest:
        """
        Approve a wallet change request.

        Args:
            request_id: Request ID to approve
            admin_id: Admin ID who is approving
            admin_notes: Optional admin notes (currently not used)

        Returns:
            Approved request

        Raises:
            ValueError: If request not found or cannot be approved
        """
        # Note: admin_notes parameter is reserved for future use
        _ = admin_notes  # Mark as intentionally unused

        request = await self.repository.get_by_id(request_id)

        if not request:
            raise ValueError(f"Request {request_id} not found")

        if request.status != WalletChangeStatus.PENDING.value:
            raise ValueError(
                f"Request {request_id} is not pending "
                f"(status: {request.status})"
            )

        # Update request
        updated_request = await self.repository.update(
            request.id,
            status=WalletChangeStatus.APPROVED.value,
            approved_by_admin_id=admin_id,
            approved_at=datetime.now(UTC),
        )

        if updated_request is None:
            raise ValueError(
                f"Failed to approve request {request_id}: update returned None"
            )

        return updated_request

    async def reject_request(
        self,
        request_id: int,
        admin_id: int,
        admin_notes: str | None = None,
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
        update_data: dict[str, Any] = {
            "status": WalletChangeStatus.REJECTED.value,
            "approved_by_admin_id": admin_id,
            "approved_at": datetime.now(UTC),
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
        updated_request = await self.repository.update(
            request.id,
            **update_data,
        )

        if updated_request is None:
            raise ValueError(
                f"Failed to reject request {request_id}: update returned None"
            )

        return updated_request
