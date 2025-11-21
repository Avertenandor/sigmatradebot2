"""Unit tests for :mod:`app.services.wallet_admin_service`."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Admin, WalletChangeRequest
from app.models.enums import WalletChangeStatus
from app.services.wallet_admin_service import WalletAdminService


@pytest.mark.asyncio
async def test_get_pending_requests_returns_only_pending(
    db_session: AsyncSession,
    test_admin: Admin,
) -> None:
    """Service should filter non-pending requests."""
    pending = WalletChangeRequest(
        type="system_deposit",
        new_address="0x" + "a" * 40,
        initiated_by_admin_id=test_admin.id,
        status=WalletChangeStatus.PENDING.value,
    )
    approved = WalletChangeRequest(
        type="system_deposit",
        new_address="0x" + "b" * 40,
        initiated_by_admin_id=test_admin.id,
        status=WalletChangeStatus.APPROVED.value,
    )
    db_session.add_all([pending, approved])
    await db_session.commit()

    service = WalletAdminService(db_session)
    pending_requests = await service.get_pending_requests()

    assert len(pending_requests) == 1
    assert pending_requests[0].id == pending.id


async def _create_admin(
    db_session: AsyncSession,
    index: int,
) -> Admin:
    admin = Admin(
        telegram_id=800000000 + index,
        username=f"approver{index}",
        role="super_admin",
        master_key="hash",
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.mark.asyncio
async def test_approve_request_updates_status(
    db_session: AsyncSession,
    test_wallet_change_request: WalletChangeRequest,
) -> None:
    """Approve flow should stamp metadata and status."""
    approver = await _create_admin(db_session, 1)
    service = WalletAdminService(db_session)

    updated = await service.approve_request(
        request_id=test_wallet_change_request.id,
        admin_id=approver.id,
    )

    assert updated.status == WalletChangeStatus.APPROVED.value
    assert updated.approved_by_admin_id == approver.id
    assert updated.approved_at is not None


@pytest.mark.asyncio
async def test_reject_request_appends_admin_notes(
    db_session: AsyncSession,
    test_wallet_change_request: WalletChangeRequest,
) -> None:
    """Admin notes must be appended to the reason."""
    service = WalletAdminService(db_session)

    updated = await service.reject_request(
        request_id=test_wallet_change_request.id,
        admin_id=test_wallet_change_request.initiated_by_admin_id,
        admin_notes="Address mismatch",
    )

    assert "Address mismatch" in (updated.reason or "")
    assert updated.status == WalletChangeStatus.REJECTED.value


@pytest.mark.asyncio
async def test_reject_request_blocks_applied_status(
    db_session: AsyncSession,
    test_admin: Admin,
) -> None:
    """Cannot reject requests already applied."""
    request = WalletChangeRequest(
        type="system_deposit",
        new_address="0x" + "c" * 40,
        initiated_by_admin_id=test_admin.id,
        status=WalletChangeStatus.APPLIED.value,
    )
    db_session.add(request)
    await db_session.commit()

    service = WalletAdminService(db_session)

    with pytest.raises(ValueError) as exc:
        await service.reject_request(
            request_id=request.id,
            admin_id=test_admin.id,
        )

    assert "cannot be rejected" in str(exc.value)
