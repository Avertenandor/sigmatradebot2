"""
Tests for admin role source consistency.

Tests that admin rights come ONLY from Admin table, not from user.is_admin flag.
"""

import pytest
from aiogram.types import Message, User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.models.user import User
from app.repositories.admin_repository import AdminRepository
from app.repositories.user_repository import UserRepository
from bot.middlewares.auth import AuthMiddleware


@pytest.mark.security
@pytest.mark.asyncio
async def test_user_with_is_admin_flag_but_no_admin_table_entry(
    db_session: AsyncSession,
) -> None:
    """
    Test that user.is_admin=True without Admin table entry does NOT grant admin rights.
    
    Scenario:
    1. Create user with is_admin=True
    2. NO entry in Admin table
    3. Process message through AuthMiddleware
    4. Verify: data["is_admin"] == False, data["admin_id"] == 0
    """
    # Create user with is_admin=True
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=123456789,
        wallet_address="0x1234567890123456789012345678901234567890",
        financial_password_hash="test_hash",
        is_admin=True,  # Set flag but no Admin table entry
    )
    await db_session.commit()
    
    # Verify no Admin table entry exists
    admin_repo = AdminRepository(db_session)
    admin = await admin_repo.get_by_telegram_id(user.telegram_id)
    assert admin is None, "No admin entry should exist"
    
    # Create middleware
    middleware = AuthMiddleware()
    
    # Create message
    message = Message(
        from_user=TelegramUser(
            id=user.telegram_id,
            is_bot=False,
            first_name="Test",
        ),
        text="/start",
        message_id=1,
        date=None,
        chat=None,
    )
    
    # Prepare data
    data = {
        "session": db_session,
        "event_from_user": message.from_user,
    }
    
    # Mock handler
    async def mock_handler(event, data):
        return "handled"
    
    # Process through middleware
    await middleware(mock_handler, message, data)
    
    # Verify: is_admin should be False (Admin table is authoritative)
    assert data["is_admin"] is False, "is_admin should be False without Admin table entry"
    assert data["admin_id"] == 0, "admin_id should be 0 without Admin table entry"
    assert data["admin"] is None, "admin object should be None"


@pytest.mark.security
@pytest.mark.asyncio
async def test_admin_table_entry_grants_admin_rights_despite_user_flag(
    db_session: AsyncSession,
) -> None:
    """
    Test that Admin table entry grants admin rights even if user.is_admin=False.
    
    Scenario:
    1. Create user with is_admin=False
    2. Create entry in Admin table
    3. Process message through AuthMiddleware
    4. Verify: data["is_admin"] == True, data["admin_id"] == admin.id
    """
    # Create user with is_admin=False
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=123456789,
        wallet_address="0x1234567890123456789012345678901234567890",
        financial_password_hash="test_hash",
        is_admin=False,  # Flag is False
    )
    await db_session.commit()
    
    # Create Admin table entry
    admin_repo = AdminRepository(db_session)
    admin = await admin_repo.create(
        telegram_id=user.telegram_id,
        role="admin",
        master_key="test_master_key_hash",
    )
    await db_session.commit()
    
    # Create middleware
    middleware = AuthMiddleware()
    
    # Create message
    message = Message(
        from_user=TelegramUser(
            id=user.telegram_id,
            is_bot=False,
            first_name="Test",
        ),
        text="/start",
        message_id=1,
        date=None,
        chat=None,
    )
    
    # Prepare data
    data = {
        "session": db_session,
        "event_from_user": message.from_user,
    }
    
    # Mock handler
    async def mock_handler(event, data):
        return "handled"
    
    # Process through middleware
    await middleware(mock_handler, message, data)
    
    # Verify: is_admin should be True (Admin table is authoritative)
    assert data["is_admin"] is True, "is_admin should be True with Admin table entry"
    assert data["admin_id"] == admin.id, "admin_id should match admin.id"
    assert data["admin"] is not None, "admin object should be set"
    assert data["admin"].id == admin.id, "admin object should match Admin table entry"


@pytest.mark.security
@pytest.mark.asyncio
async def test_no_user_no_admin_table_entry_no_admin_rights(
    db_session: AsyncSession,
) -> None:
    """
    Test that unregistered user without Admin table entry has no admin rights.
    
    Scenario:
    1. No user in database
    2. No Admin table entry
    3. Process message through AuthMiddleware
    4. Verify: data["is_admin"] == False, data["admin_id"] == 0
    """
    # Create middleware
    middleware = AuthMiddleware()
    
    # Create message from unregistered user
    message = Message(
        from_user=TelegramUser(
            id=999999999,  # Not in database
            is_bot=False,
            first_name="Unregistered",
        ),
        text="/start",
        message_id=1,
        date=None,
        chat=None,
    )
    
    # Prepare data
    data = {
        "session": db_session,
        "event_from_user": message.from_user,
    }
    
    # Mock handler
    async def mock_handler(event, data):
        return "handled"
    
    # Process through middleware
    await middleware(mock_handler, message, data)
    
    # Verify: no admin rights
    assert data["is_admin"] is False, "Unregistered user should not have admin rights"
    assert data["admin_id"] == 0, "admin_id should be 0 for unregistered user"
    assert data["admin"] is None, "admin object should be None"

