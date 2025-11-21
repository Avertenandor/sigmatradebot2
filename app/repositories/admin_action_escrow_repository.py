"""
AdminActionEscrow repository.

R18-4: Repository for dual control escrow records.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_action_escrow import AdminActionEscrow


class AdminActionEscrowRepository:
    """Repository for AdminActionEscrow operations."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository.

        Args:
            session: Database session
        """
        self.session = session

    async def create(
        self,
        operation_type: str,
        target_id: int | None,
        operation_data: dict[str, Any],
        initiator_admin_id: int,
        expires_in_hours: int = 24,
    ) -> AdminActionEscrow:
        """
        Create new escrow record.

        Args:
            operation_type: Type of operation
            target_id: Target resource ID
            operation_data: Operation data (JSON)
            initiator_admin_id: Admin who initiated
            expires_in_hours: Expiry time in hours

        Returns:
            Created escrow record
        """
        expires_at = datetime.now(UTC) + timedelta(hours=expires_in_hours)

        escrow = AdminActionEscrow(
            operation_type=operation_type,
            target_id=target_id,
            operation_data=operation_data,
            initiator_admin_id=initiator_admin_id,
            status="PENDING",
            expires_at=expires_at,
        )

        self.session.add(escrow)
        await self.session.flush()
        return escrow

    async def get_by_id(self, escrow_id: int) -> AdminActionEscrow | None:
        """
        Get escrow by ID.

        Args:
            escrow_id: Escrow ID

        Returns:
            Escrow record or None
        """
        stmt = select(AdminActionEscrow).where(
            AdminActionEscrow.id == escrow_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_by_operation(
        self,
        operation_type: str,
        target_id: int,
    ) -> AdminActionEscrow | None:
        """
        Get pending escrow for operation.

        Args:
            operation_type: Type of operation
            target_id: Target resource ID

        Returns:
            Pending escrow or None
        """
        stmt = (
            select(AdminActionEscrow)
            .where(
                AdminActionEscrow.operation_type == operation_type,
                AdminActionEscrow.target_id == target_id,
                AdminActionEscrow.status == "PENDING",
            )
            .order_by(AdminActionEscrow.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def approve(
        self,
        escrow_id: int,
        approver_admin_id: int,
    ) -> AdminActionEscrow | None:
        """
        Approve escrow (second admin).

        Args:
            escrow_id: Escrow ID
            approver_admin_id: Admin who approves

        Returns:
            Updated escrow or None if not found
        """
        escrow = await self.get_by_id(escrow_id)
        if not escrow:
            return None

        if escrow.status != "PENDING":
            return None

        if escrow.initiator_admin_id == approver_admin_id:
            # Cannot approve own initiation
            return None

        escrow.approver_admin_id = approver_admin_id
        escrow.status = "APPROVED"
        escrow.approved_at = datetime.now(UTC)

        await self.session.flush()
        return escrow

    async def reject(
        self,
        escrow_id: int,
        approver_admin_id: int,
        reason: str,
    ) -> AdminActionEscrow | None:
        """
        Reject escrow (second admin).

        Args:
            escrow_id: Escrow ID
            approver_admin_id: Admin who rejects
            reason: Rejection reason

        Returns:
            Updated escrow or None if not found
        """
        escrow = await self.get_by_id(escrow_id)
        if not escrow:
            return None

        if escrow.status != "PENDING":
            return None

        escrow.approver_admin_id = approver_admin_id
        escrow.status = "REJECTED"
        escrow.rejection_reason = reason

        await self.session.flush()
        return escrow

    async def get_expired_pending(self) -> list[AdminActionEscrow]:
        """
        Get expired pending escrows.

        Returns:
            List of expired escrows
        """
        now = datetime.now(UTC)
        stmt = (
            select(AdminActionEscrow)
            .where(
                AdminActionEscrow.status == "PENDING",
                AdminActionEscrow.expires_at < now,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_expired(self, escrow_id: int) -> None:
        """
        Mark escrow as expired.

        Args:
            escrow_id: Escrow ID
        """
        escrow = await self.get_by_id(escrow_id)
        if escrow and escrow.status == "PENDING":
            escrow.status = "EXPIRED"
            await self.session.flush()

