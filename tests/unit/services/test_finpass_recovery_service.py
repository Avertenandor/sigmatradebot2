"""Unit tests for :mod:`app.services.finpass_recovery_service`."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services.finpass_recovery_service import (
    FinpassRecoveryService,
    FinancialRecoveryStatus,
)


@pytest.mark.asyncio
async def test_create_recovery_request_success(
    db_session: AsyncSession, test_user: User
) -> None:
    """Creating a request should persist pending entry with proper flags."""
    service = FinpassRecoveryService(db_session)

    request = await service.create_recovery_request(
        user_id=test_user.id,
        reason="Lost access to my device and need reset",
        video_required=False,
    )

    assert request.user_id == test_user.id
    assert request.status == FinancialRecoveryStatus.PENDING.value
    assert request.video_required is False
    assert request.video_verified is True


@pytest.mark.asyncio
async def test_create_recovery_request_requires_unique_pending(
    db_session: AsyncSession, test_user: User
) -> None:
    """Second pending request for same user must be rejected."""
    service = FinpassRecoveryService(db_session)
    await service.create_recovery_request(
        user_id=test_user.id,
        reason="Device lost, requesting reset",
    )

    with pytest.raises(ValueError) as exc:
        await service.create_recovery_request(
            user_id=test_user.id,
            reason="Need another reset immediately",
        )

    assert "pending recovery request" in str(exc.value)


@pytest.mark.asyncio
async def test_create_recovery_request_reason_length_validation(
    db_session: AsyncSession, test_user: User
) -> None:
    """Reason shorter than 10 characters should raise validation error."""
    service = FinpassRecoveryService(db_session)

    with pytest.raises(ValueError) as exc:
        await service.create_recovery_request(
            user_id=test_user.id,
            reason="short",
        )

    assert "at least 10 characters" in str(exc.value)


@pytest.mark.asyncio
async def test_has_active_recovery_detects_non_pending_status(
    db_session: AsyncSession, test_user: User
) -> None:
    """Approved/in-review/sent statuses must be treated as active."""
    service = FinpassRecoveryService(db_session)
    request = await service.create_recovery_request(
        user_id=test_user.id,
        reason="Need reset after phone break",
    )

    # Simulate admin taking action -> mark as in review
    await service.repository.update(
        request.id, status=FinancialRecoveryStatus.IN_REVIEW.value
    )

    assert await service.has_active_recovery(test_user.id) is True


@pytest.mark.asyncio
async def test_approve_and_mark_sent_flow(
    db_session: AsyncSession, test_user: User
) -> None:
    """Approve -> mark sent should update status and admin metadata."""
    service = FinpassRecoveryService(db_session)
    request = await service.create_recovery_request(
        user_id=test_user.id,
        reason="Lost MFA device and need password resend",
    )

    admin_id = 42
    approved = await service.approve_request(
        request_id=request.id,
        admin_id=admin_id,
        admin_notes="Documents verified",
    )

    assert approved.status == FinancialRecoveryStatus.APPROVED.value
    assert approved.processed_by_admin_id == admin_id
    assert approved.admin_comment == "Documents verified"
    assert approved.processed_at is not None

    sent = await service.mark_sent(
        request_id=request.id,
        admin_id=admin_id,
        admin_notes="Password delivered",
    )

    assert sent.status == FinancialRecoveryStatus.SENT.value
    assert sent.admin_comment == "Password delivered"


@pytest.mark.asyncio
async def test_reject_request_from_pending(
    db_session: AsyncSession, test_user: User
) -> None:
    """Pending requests can be rejected with audit trail."""
    service = FinpassRecoveryService(db_session)
    request = await service.create_recovery_request(
        user_id=test_user.id,
        reason="Provided evidence not sufficient",
    )

    result = await service.reject_request(
        request_id=request.id,
        admin_id=99,
        admin_notes="Insufficient KYC",
    )

    assert result.status == FinancialRecoveryStatus.REJECTED.value
    assert result.admin_comment == "Insufficient KYC"
