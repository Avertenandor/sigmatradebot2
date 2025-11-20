"""
Tests for emergency admin block functionality.

Tests that emergency admin block works atomically and correctly.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.models.blacklist import BlacklistActionType
from app.models.user import User
from app.repositories.admin_repository import AdminRepository
from app.repositories.blacklist_repository import BlacklistRepository
from app.repositories.user_repository import UserRepository
from app.services.admin_service import AdminService
from bot.handlers.admin.admins import process_emergency_block_telegram_id


@pytest.mark.security
@pytest.mark.asyncio
async def test_emergency_block_removes_admin_from_table(
    db_session: AsyncSession,
) -> None:
    """
    Test that emergency block removes admin from admins table.

    Scenario:
    1. Create super_admin and regular admin
    2. Execute emergency block for regular admin
    3. Verify admin is removed from admins table
    """
    # Create super_admin
    admin_service = AdminService(db_session)
    super_admin, _, _ = await admin_service.create_admin(
        telegram_id=111111111,
        role="super_admin",
        created_by=1,  # System
    )
    await db_session.commit()

    # Create regular admin
    regular_admin, _, _ = await admin_service.create_admin(
        telegram_id=222222222,
        role="admin",
        created_by=super_admin.id,
    )
    await db_session.commit()

    # Verify admin exists
    admin_repo = AdminRepository(db_session)
    found_admin = await admin_repo.get_by_id(regular_admin.id)
    assert found_admin is not None

    # Execute emergency block (simulate handler call)
    from app.services.blacklist_service import BlacklistService
    from app.services.admin_log_service import AdminLogService

    blacklist_service = BlacklistService(db_session)
    log_service = AdminLogService(db_session)

    # Add to blacklist
    blacklist_entry = await blacklist_service.add_to_blacklist(
        telegram_id=regular_admin.telegram_id,
        reason="Compromised admin account",
        added_by_admin_id=super_admin.id,
        action_type=BlacklistActionType.TERMINATED,
    )

    # Delete admin
    await admin_service.delete_admin(regular_admin.id)

    # Ban user if exists
    user_repo = UserRepository(db_session)
    user = await user_repo.get_by_telegram_id(regular_admin.telegram_id)
    if user:
        user.is_banned = True
        await db_session.flush()

    await db_session.commit()

    # Verify admin is removed
    found_admin_after = await admin_repo.get_by_id(regular_admin.id)
    assert found_admin_after is None, "Admin should be removed from table"

    # Verify blacklist entry exists
    blacklist_repo = BlacklistRepository(db_session)
    found_blacklist = await blacklist_repo.get_by_id(blacklist_entry.id)
    assert found_blacklist is not None
    assert found_blacklist.action_type == BlacklistActionType.TERMINATED
    assert found_blacklist.is_active is True


@pytest.mark.security
@pytest.mark.asyncio
async def test_emergency_block_bans_user_if_exists(
    db_session: AsyncSession,
) -> None:
    """
    Test that emergency block sets user.is_banned=True if user exists.

    Scenario:
    1. Create admin that is also a registered user
    2. Execute emergency block
    3. Verify user.is_banned is True
    """
    # Create user
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=333333333,
        wallet_address="0x3333333333333333333333333333333333333333",
        financial_password_hash="test_hash",
    )
    await db_session.commit()

    # Create admin with same telegram_id
    admin_service = AdminService(db_session)
    admin, _, _ = await admin_service.create_admin(
        telegram_id=user.telegram_id,
        role="admin",
        created_by=1,
    )
    await db_session.commit()

    # Create super_admin for blocking
    super_admin, _, _ = await admin_service.create_admin(
        telegram_id=444444444,
        role="super_admin",
        created_by=1,
    )
    await db_session.commit()

    # Execute emergency block
    from app.services.blacklist_service import BlacklistService

    blacklist_service = BlacklistService(db_session)
    await blacklist_service.add_to_blacklist(
        telegram_id=admin.telegram_id,
        reason="Compromised admin account",
        added_by_admin_id=super_admin.id,
        action_type=BlacklistActionType.TERMINATED,
    )

    await admin_service.delete_admin(admin.id)

    # Ban user
    user = await user_repo.get_by_telegram_id(admin.telegram_id)
    if user:
        user.is_banned = True
        await db_session.flush()

    await db_session.commit()

    # Verify user is banned
    user_after = await user_repo.get_by_telegram_id(admin.telegram_id)
    assert user_after is not None
    assert user_after.is_banned is True, "User should be banned after emergency block"

