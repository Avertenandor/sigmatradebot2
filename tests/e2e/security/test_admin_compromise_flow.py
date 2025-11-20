"""
E2E tests for admin compromise scenario.

Tests the complete flow of emergency admin blocking:
1. Admin is compromised
2. Super admin blocks the compromised admin
3. Admin is removed from admins table
4. Blacklist entry with TERMINATED is created
5. User is banned (if exists)
6. BanMiddleware blocks all updates from blocked admin
"""

import pytest
from aiogram.types import Message, User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.models.blacklist import BlacklistActionType
from app.models.user import User
from app.repositories.admin_repository import AdminRepository
from app.repositories.blacklist_repository import BlacklistRepository
from app.repositories.user_repository import UserRepository
from app.services.admin_service import AdminService
from app.services.blacklist_service import BlacklistService
from bot.middlewares.ban_middleware import BanMiddleware


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_emergency_admin_block_complete_flow(
    db_session: AsyncSession,
) -> None:
    """
    Test complete flow of emergency admin blocking.

    Scenario:
    GIVEN: super_admin and regular admin exist in system
    WHEN: super_admin executes emergency block for regular admin
    THEN:
        - admin is removed from admins table
        - blacklist entry with TERMINATED is created
        - if user exists with this telegram_id → is_banned=True
        - BanMiddleware blocks all messages from this telegram_id
    """
    # GIVEN: Create super_admin
    admin_service = AdminService(db_session)
    super_admin, _, _ = await admin_service.create_admin(
        telegram_id=111111111,
        role="super_admin",
        created_by=1,  # System
    )
    await db_session.commit()

    # GIVEN: Create regular admin
    regular_admin, _, _ = await admin_service.create_admin(
        telegram_id=222222222,
        role="admin",
        created_by=super_admin.id,
    )
    await db_session.commit()

    # Verify admin exists
    admin_repo = AdminRepository(db_session)
    found_admin = await admin_repo.get_by_id(regular_admin.id)
    assert found_admin is not None, "Admin should exist before blocking"

    # WHEN: Execute emergency block
    blacklist_service = BlacklistService(db_session)

    # Step 1: Add to blacklist with TERMINATED
    blacklist_entry = await blacklist_service.add_to_blacklist(
        telegram_id=regular_admin.telegram_id,
        reason="Compromised admin account - emergency block",
        added_by_admin_id=super_admin.id,
        action_type=BlacklistActionType.TERMINATED,
    )

    # Step 2: Delete admin from admins table
    await admin_service.delete_admin(regular_admin.id)

    # Step 3: Ban user if exists
    user_repo = UserRepository(db_session)
    user = await user_repo.get_by_telegram_id(regular_admin.telegram_id)
    if user:
        user.is_banned = True
        await db_session.flush()

    await db_session.commit()

    # THEN: Verify admin is removed from admins table
    found_admin_after = await admin_repo.get_by_id(regular_admin.id)
    assert found_admin_after is None, "Admin should be removed from admins table"

    # THEN: Verify blacklist entry exists with TERMINATED
    blacklist_repo = BlacklistRepository(db_session)
    found_blacklist = await blacklist_repo.get_by_id(blacklist_entry.id)
    assert found_blacklist is not None, "Blacklist entry should exist"
    assert (
        found_blacklist.action_type == BlacklistActionType.TERMINATED
    ), "Blacklist entry should have TERMINATED action type"
    assert found_blacklist.is_active is True, "Blacklist entry should be active"
    assert (
        found_blacklist.telegram_id == regular_admin.telegram_id
    ), "Blacklist entry should have correct telegram_id"

    # THEN: Verify user is banned (if exists)
    if user:
        user_after = await user_repo.get_by_telegram_id(regular_admin.telegram_id)
        assert user_after is not None, "User should exist"
        assert user_after.is_banned is True, "User should be banned after emergency block"


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_blocked_admin_cannot_login(
    db_session: AsyncSession,
) -> None:
    """
    Test that blocked admin cannot login.

    Scenario:
    GIVEN: Admin is emergency blocked (TERMINATED)
    WHEN: Admin tries to login (send /start)
    THEN: Admin cannot login (not in admins table)
    """
    # GIVEN: Create super_admin and regular admin
    admin_service = AdminService(db_session)
    super_admin, _, _ = await admin_service.create_admin(
        telegram_id=333333333,
        role="super_admin",
        created_by=1,
    )
    await db_session.commit()

    regular_admin, _, _ = await admin_service.create_admin(
        telegram_id=444444444,
        role="admin",
        created_by=super_admin.id,
    )
    await db_session.commit()

    # GIVEN: Execute emergency block
    blacklist_service = BlacklistService(db_session)
    await blacklist_service.add_to_blacklist(
        telegram_id=regular_admin.telegram_id,
        reason="Compromised admin",
        added_by_admin_id=super_admin.id,
        action_type=BlacklistActionType.TERMINATED,
    )
    await admin_service.delete_admin(regular_admin.id)
    await db_session.commit()

    # WHEN: Try to find admin in admins table
    admin_repo = AdminRepository(db_session)
    found_admin = await admin_repo.get_by_telegram_id(regular_admin.telegram_id)

    # THEN: Admin should not be found
    assert found_admin is None, "Blocked admin should not be in admins table"


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_blocked_admin_middleware_blocks_updates(
    db_session: AsyncSession,
) -> None:
    """
    Test that BanMiddleware blocks all updates from blocked admin.

    Scenario:
    GIVEN: Admin is emergency blocked (TERMINATED)
    WHEN: Admin sends any message
    THEN: BanMiddleware blocks update (returns None, handler not called)
    """
    # GIVEN: Create super_admin and regular admin
    admin_service = AdminService(db_session)
    super_admin, _, _ = await admin_service.create_admin(
        telegram_id=555555555,
        role="super_admin",
        created_by=1,
    )
    await db_session.commit()

    regular_admin, _, _ = await admin_service.create_admin(
        telegram_id=666666666,
        role="admin",
        created_by=super_admin.id,
    )
    await db_session.commit()

    # GIVEN: Create user with same telegram_id (admin is also a user)
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=regular_admin.telegram_id,
        wallet_address="0x6666666666666666666666666666666666666666",
        financial_password_hash="test_hash",
    )
    await db_session.commit()

    # GIVEN: Execute emergency block
    blacklist_service = BlacklistService(db_session)
    await blacklist_service.add_to_blacklist(
        telegram_id=regular_admin.telegram_id,
        reason="Compromised admin",
        added_by_admin_id=super_admin.id,
        action_type=BlacklistActionType.TERMINATED,
    )
    await admin_service.delete_admin(regular_admin.id)
    user.is_banned = True
    await db_session.commit()

    # WHEN: Admin tries to send message
    middleware = BanMiddleware()

    # Create mock handler that should NOT be called
    handler_called = False

    async def mock_handler(event, data):
        nonlocal handler_called
        handler_called = True
        return "handler_result"

    # Create mock message event
    telegram_user = TelegramUser(
        id=regular_admin.telegram_id,
        is_bot=False,
        first_name="Blocked",
        last_name="Admin",
    )
    message = Message(
        message_id=1,
        date=None,
        chat=None,
        from_user=telegram_user,
        text="/start",
    )

    # Prepare data
    data = {
        "event_from_user": telegram_user,
        "session": db_session,
    }

    # Execute middleware
    result = await middleware(mock_handler, message, data)

    # THEN: Handler should NOT be called (returns None)
    assert handler_called is False, "Handler should not be called for TERMINATED user"
    assert result is None, "Middleware should return None for TERMINATED user"


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_blocked_admin_with_user_account(
    db_session: AsyncSession,
) -> None:
    """
    Test emergency block when admin is also a registered user.

    Scenario:
    GIVEN: Admin is also a registered user
    WHEN: Super admin blocks the admin
    THEN:
        - Admin is removed from admins table
        - User.is_banned is set to True
        - Blacklist entry with TERMINATED is created
    """
    # GIVEN: Create user
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=777777777,
        wallet_address="0x7777777777777777777777777777777777777777",
        financial_password_hash="test_hash",
    )
    await db_session.commit()

    # GIVEN: Create admin with same telegram_id
    admin_service = AdminService(db_session)
    super_admin, _, _ = await admin_service.create_admin(
        telegram_id=888888888,
        role="super_admin",
        created_by=1,
    )
    await db_session.commit()

    admin, _, _ = await admin_service.create_admin(
        telegram_id=user.telegram_id,
        role="admin",
        created_by=super_admin.id,
    )
    await db_session.commit()

    # WHEN: Execute emergency block
    blacklist_service = BlacklistService(db_session)
    blacklist_entry = await blacklist_service.add_to_blacklist(
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

    # THEN: Verify admin is removed
    admin_repo = AdminRepository(db_session)
    found_admin = await admin_repo.get_by_telegram_id(admin.telegram_id)
    assert found_admin is None, "Admin should be removed"

    # THEN: Verify user is banned
    user_after = await user_repo.get_by_telegram_id(admin.telegram_id)
    assert user_after is not None, "User should exist"
    assert user_after.is_banned is True, "User should be banned"

    # THEN: Verify blacklist entry
    blacklist_repo = BlacklistRepository(db_session)
    found_blacklist = await blacklist_repo.get_by_id(blacklist_entry.id)
    assert found_blacklist is not None, "Blacklist entry should exist"
    assert (
        found_blacklist.action_type == BlacklistActionType.TERMINATED
    ), "Should be TERMINATED"

