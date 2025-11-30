# MCP-MARKER:CREATE:FINPASS_RECOVERY_SERVICE
# MCP-ANCHOR: finpass-recovery-service
# MCP-DEPS: [sqlalchemy, loguru]
# MCP-PROVIDES: FinpassRecoveryService, FinancialRecoveryStatus
# MCP-SUMMARY: Service layer for handling financial password recovery workflow.
"""Finpass recovery service.

Business logic for managing financial password recovery requests.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_password_recovery import (
    FinancialPasswordRecovery,
)
from app.repositories.financial_password_recovery_repository import (
    FinancialPasswordRecoveryRepository,
)
from app.repositories.user_repository import UserRepository


class FinancialRecoveryStatus(StrEnum):
    """Lifecycle states for a financial password recovery request."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"


# Active statuses that block new requests (NOT including SENT - that's completed)
ACTIVE_USER_STATUSES: tuple[FinancialRecoveryStatus, ...] = (
    FinancialRecoveryStatus.PENDING,
    FinancialRecoveryStatus.IN_REVIEW,
    FinancialRecoveryStatus.APPROVED,
)


class FinpassRecoveryService:
    """Service wrapper around financial password recovery workflow."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the service with required repositories."""
        self.session = session
        self.repository = FinancialPasswordRecoveryRepository(session)
        self.user_repository = UserRepository(session)

    async def get_pending_by_user(
        self, user_id: int
    ) -> FinancialPasswordRecovery | None:
        """Return the pending request for a user, if any."""
        requests = await self.repository.get_by_user(
            user_id=user_id,
            status=FinancialRecoveryStatus.PENDING.value,
        )
        return requests[0] if requests else None

    async def has_active_recovery(self, user_id: int) -> bool:
        """Check whether a user already has an active recovery process."""
        stmt = (
            select(FinancialPasswordRecovery.id)
            .where(FinancialPasswordRecovery.user_id == user_id)
            .where(
                FinancialPasswordRecovery.status.in_(
                    [status.value for status in ACTIVE_USER_STATUSES]
                )
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create_recovery_request(
        self,
        *,
        user_id: int,
        reason: str,
        video_required: bool = True,
    ) -> FinancialPasswordRecovery:
        """Create a new financial password recovery request."""
        normalized_reason = reason.strip()
        if len(normalized_reason) < 10:
            raise ValueError(
                "Recovery reason must contain at least 10 characters"
            )

        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if await self.get_pending_by_user(user_id):
            raise ValueError(
                "A pending recovery request already exists for this user"
            )

        if await self.has_active_recovery(user_id):
            raise ValueError(
                "You already have an active recovery request awaiting "
                "completion"
            )

        request = await self.repository.create(
            user_id=user_id,
            reason=normalized_reason,
            status=FinancialRecoveryStatus.PENDING.value,
            video_required=video_required,
            video_verified=not video_required,
        )

        # Block earnings immediately upon creating recovery request
        # This prevents any new earnings while recovery is in progress
        from app.services.user_service import UserService

        user_service = UserService(self.session)
        await user_service.block_earnings(user_id, block=True)
        logger.info(
            "Earnings blocked for user due to finpass recovery request",
            extra={"user_id": user_id, "request_id": request.id},
        )

        logger.info(
            "Created financial password recovery request",
            extra={
                "user_id": user_id,
                "request_id": request.id,
                "video_required": video_required,
            },
        )

        return request

    async def get_all_pending(
        self, limit: int | None = None
    ) -> list[FinancialPasswordRecovery]:
        """Fetch pending requests, optionally limited for admin UI."""
        if limit is None:
            return await self.repository.get_pending_requests()

        stmt = (
            select(FinancialPasswordRecovery)
            .where(
                FinancialPasswordRecovery.status
                == FinancialRecoveryStatus.PENDING.value
            )
            .order_by(FinancialPasswordRecovery.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def approve_request(
        self,
        *,
        request_id: int,
        admin_id: int,
        admin_notes: str | None = None,
    ) -> FinancialPasswordRecovery:
        """Approve a recovery request."""
        request = await self._get_request(request_id)
        self._ensure_status(
            request,
            allowed={
                FinancialRecoveryStatus.PENDING,
                FinancialRecoveryStatus.IN_REVIEW,
            },
            action="approve",
        )

        updated = await self.repository.update(
            request.id,
            status=FinancialRecoveryStatus.APPROVED.value,
            processed_by_admin_id=admin_id,
            processed_at=datetime.now(UTC),
            admin_comment=admin_notes,
        )

        logger.info(
            "Approved financial password recovery request",
            extra={
                "request_id": request_id,
                "admin_id": admin_id,
            },
        )
        return updated or request

    async def reject_request(
        self,
        *,
        request_id: int,
        admin_id: int | None = None,
        admin_notes: str | None = None,
    ) -> FinancialPasswordRecovery:
        """
        Reject a recovery request.

        Args:
            request_id: Recovery request ID
            admin_id: Admin ID (optional, None for system rejection)
            admin_notes: Admin notes (optional)
        """
        request = await self._get_request(request_id)
        self._ensure_status(
            request,
            allowed={
                FinancialRecoveryStatus.PENDING,
                FinancialRecoveryStatus.IN_REVIEW,
                FinancialRecoveryStatus.APPROVED,
            },
            action="reject",
        )

        updated = await self.repository.update(
            request.id,
            status=FinancialRecoveryStatus.REJECTED.value,
            processed_by_admin_id=admin_id,
            processed_at=datetime.now(UTC),
            admin_comment=admin_notes,
        )

        logger.info(
            "Rejected financial password recovery request",
            extra={
                "request_id": request_id,
                "admin_id": admin_id,
            },
        )
        return updated or request

    async def mark_sent(
        self,
        *,
        request_id: int,
        admin_id: int,
        admin_notes: str | None = None,
    ) -> FinancialPasswordRecovery:
        """Mark an approved request as sent to the user."""
        request = await self._get_request(request_id)
        self._ensure_status(
            request,
            allowed={FinancialRecoveryStatus.APPROVED},
            action="mark as sent",
        )

        updated = await self.repository.update(
            request.id,
            status=FinancialRecoveryStatus.SENT.value,
            processed_by_admin_id=admin_id,
            processed_at=datetime.now(UTC),
            admin_comment=admin_notes,
        )

        logger.info(
            "Marked financial password recovery request as sent",
            extra={
                "request_id": request_id,
                "admin_id": admin_id,
            },
        )
        return updated or request

    async def get_request_by_id(
        self, request_id: int
    ) -> FinancialPasswordRecovery | None:
        """Get a request by ID."""
        return await self.repository.get_by_id(request_id)

    async def _get_request(
        self, request_id: int
    ) -> FinancialPasswordRecovery:
        request = await self.repository.get_by_id(request_id)
        if not request:
            raise ValueError(f"Recovery request {request_id} not found")
        return request

    @staticmethod
    def _ensure_status(
        request: FinancialPasswordRecovery,
        *,
        allowed: Iterable[FinancialRecoveryStatus],
        action: str,
    ) -> None:
        allowed_values = {status.value for status in allowed}
        if request.status not in allowed_values:
            raise ValueError(

                    f"Cannot {action} request {request.id} "
                    f"in status {request.status}"

            )
