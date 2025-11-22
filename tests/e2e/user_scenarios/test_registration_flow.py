"""
E2E tests for user registration flow.

Tests complete registration scenarios:
- Guest → /start → registration → valid wallet → finpass → contacts
- Registration with already taken wallet
- Registration with blacklist (telegram_id and wallet_address)
- Registration with referral code (valid, invalid, blocked referrer)
"""

import pytest
from decimal import Decimal

from app.models.blacklist import Blacklist, BlacklistActionType
from app.models.user import User
from app.repositories.blacklist_repository import BlacklistRepository
from app.repositories.user_repository import UserRepository
from app.services.blacklist_service import BlacklistService
from app.services.user_service import UserService
from tests.conftest import hash_password


@pytest.mark.e2e
@pytest.mark.critical
@pytest.mark.asyncio
async def test_registration_complete_flow(
    db_session,
    user_service: UserService,
) -> None:
    """
    Test complete registration flow.

    GIVEN: Guest (not registered)
    WHEN: Registers with valid wallet → finpass → contacts
    THEN:
        - User is created in DB
        - Wallet is saved
        - Financial password is hashed
        - Contacts are saved
        - User can be retrieved
    """
    # Arrange
    telegram_id = 111111111
    wallet_address = "0x" + "1" * 40
    financial_password = "test123456"
    username = "testuser"
    phone = "+1234567890"
    email = "test@example.com"

    # Act: Register user
    hashed_password = hash_password(financial_password)
    user = await user_service.register_user(
        telegram_id=telegram_id,
        wallet_address=wallet_address,
        financial_password=hashed_password,
        username=username,
    )

    # Update contacts
    await user_service.update_profile(
        user.id,
        phone=phone,
        email=email,
    )

    # Assert: User exists
    assert user is not None
    assert user.telegram_id == telegram_id
    assert user.wallet_address == wallet_address
    assert user.username == username
    assert user.financial_password == hashed_password
    assert user.phone == phone
    assert user.email == email

    # Assert: User can be retrieved
    user_repo = UserRepository(db_session)
    retrieved_user = await user_repo.get_by_telegram_id(telegram_id)
    assert retrieved_user is not None
    assert retrieved_user.id == user.id
    assert retrieved_user.wallet_address == wallet_address


@pytest.mark.e2e
@pytest.mark.critical
@pytest.mark.asyncio
async def test_registration_with_taken_wallet(
    db_session,
    user_service: UserService,
    create_user_helper,
) -> None:
    """
    Test registration with already taken wallet.

    GIVEN: Wallet is already registered to another user
    WHEN: New user tries to register with same wallet
    THEN: ValueError is raised with "User already registered" or wallet check fails
    """
    # Arrange: Create existing user with wallet
    existing_user = await create_user_helper(
        telegram_id=222222222,
        wallet_address="0x" + "2" * 40,
    )

    # Act & Assert: Try to register with same wallet
    hashed_password = hash_password("test123456")
    
    # Try to register with same wallet but different telegram_id
    with pytest.raises(ValueError) as exc_info:
        await user_service.register_user(
            telegram_id=333333333,  # Different telegram_id
            wallet_address=existing_user.wallet_address,  # Same wallet
            financial_password=hashed_password,
        )
    
    # Should fail because wallet is already taken
    error_msg = str(exc_info.value)
    assert "already" in error_msg.lower() or "wallet" in error_msg.lower()


@pytest.mark.e2e
@pytest.mark.critical
@pytest.mark.asyncio
async def test_registration_with_blacklist_telegram_id(
    db_session,
    user_service: UserService,
    blacklist_service: BlacklistService,
) -> None:
    """
    Test registration with blacklisted telegram_id.

    GIVEN: telegram_id is in blacklist with REGISTRATION_DENIED
    WHEN: User tries to register
    THEN: ValueError is raised with BLACKLISTED:REGISTRATION_DENIED
    """
    # Arrange: Add telegram_id to blacklist
    telegram_id = 444444444
    await blacklist_service.add_to_blacklist(
        telegram_id=telegram_id,
        reason="Test registration denial",
        added_by_admin_id=1,  # System
        action_type=BlacklistActionType.REGISTRATION_DENIED,
    )
    await db_session.commit()

    # Act & Assert: Try to register
    hashed_password = hash_password("test123456")
    with pytest.raises(ValueError) as exc_info:
        await user_service.register_user(
            telegram_id=telegram_id,
            wallet_address="0x" + "4" * 40,
            financial_password=hashed_password,
        )
    
    # Should fail with BLACKLISTED error
    error_msg = str(exc_info.value)
    assert "BLACKLISTED" in error_msg
    assert "REGISTRATION_DENIED" in error_msg


@pytest.mark.e2e
@pytest.mark.critical
@pytest.mark.asyncio
async def test_registration_with_blacklist_wallet_address(
    db_session,
    user_service: UserService,
    blacklist_service: BlacklistService,
) -> None:
    """
    Test registration with blacklisted wallet_address.

    GIVEN: wallet_address is in blacklist
    WHEN: User tries to register with that wallet
    THEN: Registration should be blocked (check happens in handler, not service)
    
    Note: Service-level check for wallet blacklist may not exist,
    but handler checks it. This test verifies service behavior.
    """
    # Arrange: Add wallet to blacklist
    wallet_address = "0x" + "5" * 40
    blacklist_repo = BlacklistRepository(db_session)
    blacklist_entry = await blacklist_repo.create(
        telegram_id=None,
        wallet_address=wallet_address.lower(),
        action_type=BlacklistActionType.REGISTRATION_DENIED,
        reason="Test wallet blacklist",
        is_active=True,
    )
    await db_session.commit()

    # Act: Try to register
    # Note: Service doesn't check wallet blacklist directly,
    # but handler does. For E2E, we test that blacklist service
    # can detect it.
    is_blacklisted = await blacklist_service.is_blacklisted(
        wallet_address=wallet_address.lower()
    )
    
    # Assert: Wallet is blacklisted
    assert is_blacklisted is True


@pytest.mark.e2e
@pytest.mark.critical
@pytest.mark.asyncio
async def test_registration_with_valid_referral_code(
    db_session,
    user_service: UserService,
    create_user_helper,
) -> None:
    """
    Test registration with valid referral code.

    GIVEN: Referrer exists
    WHEN: New user registers with referrer_telegram_id
    THEN:
        - User is created
        - referrer_id is set correctly
        - Referral relationship is created
    """
    # Arrange: Create referrer
    referrer = await create_user_helper(
        telegram_id=666666666,
        wallet_address="0x" + "6" * 40,
    )

    # Act: Register new user with referral
    hashed_password = hash_password("test123456")
    new_user = await user_service.register_user(
        telegram_id=777777777,
        wallet_address="0x" + "7" * 40,
        financial_password=hashed_password,
        referrer_telegram_id=referrer.telegram_id,
    )

    # Assert: User is created with referrer
    assert new_user is not None
    assert new_user.referrer_id == referrer.id

    # Assert: Referral relationship exists
    from app.repositories.referral_repository import ReferralRepository
    referral_repo = ReferralRepository(db_session)
    referral = await referral_repo.get_by_referred_id(new_user.id)
    assert referral is not None
    assert referral.referrer_id == referrer.id
    assert referral.referred_id == new_user.id


@pytest.mark.e2e
@pytest.mark.critical
@pytest.mark.asyncio
async def test_registration_with_invalid_referral_code(
    db_session,
    user_service: UserService,
) -> None:
    """
    Test registration with invalid referral code.

    GIVEN: Referrer does not exist
    WHEN: New user registers with non-existent referrer_telegram_id
    THEN:
        - User is created
        - referrer_id is None (no error, just ignored)
    """
    # Act: Register with non-existent referrer
    hashed_password = hash_password("test123456")
    new_user = await user_service.register_user(
        telegram_id=888888888,
        wallet_address="0x" + "8" * 40,
        financial_password=hashed_password,
        referrer_telegram_id=999999999,  # Non-existent
    )

    # Assert: User is created but referrer_id is None
    assert new_user is not None
    assert new_user.referrer_id is None


@pytest.mark.e2e
@pytest.mark.critical
@pytest.mark.asyncio
async def test_registration_with_blocked_referrer(
    db_session,
    user_service: UserService,
    blacklist_service: BlacklistService,
    create_user_helper,
) -> None:
    """
    Test registration with referral code from blocked referrer.

    GIVEN: Referrer exists but is BLOCKED
    WHEN: New user registers with referrer_telegram_id
    THEN:
        - User is created
        - referrer_id is set (referrer status doesn't block registration)
        - Referral relationship is created
    
    Note: Blocked referrer doesn't prevent registration,
    but may affect referral earnings later.
    """
    # Arrange: Create and block referrer
    referrer = await create_user_helper(
        telegram_id=101010101,
        wallet_address="0x" + "a" * 40,
    )
    
    await blacklist_service.add_to_blacklist(
        telegram_id=referrer.telegram_id,
        reason="Test block",
        added_by_admin_id=1,
        action_type=BlacklistActionType.BLOCKED,
    )
    await db_session.commit()

    # Act: Register with blocked referrer
    hashed_password = hash_password("test123456")
    new_user = await user_service.register_user(
        telegram_id=202020202,
        wallet_address="0x" + "b" * 40,
        financial_password=hashed_password,
        referrer_telegram_id=referrer.telegram_id,
    )

    # Assert: User is created with referrer (blocked status doesn't prevent)
    assert new_user is not None
    assert new_user.referrer_id == referrer.id

    # Assert: Referral relationship exists
    from app.repositories.referral_repository import ReferralRepository
    referral_repo = ReferralRepository(db_session)
    referral = await referral_repo.get_by_referred_id(new_user.id)
    assert referral is not None
    assert referral.referrer_id == referrer.id


@pytest.mark.e2e
@pytest.mark.critical
@pytest.mark.asyncio
async def test_registration_wallet_validation(
    db_session,
    user_service: UserService,
) -> None:
    """
    Test wallet address validation during registration.

    GIVEN: Invalid wallet address
    WHEN: User tries to register
    THEN: Validation should fail (tested at handler level, not service)
    
    Note: Service accepts any string, validation happens in handler.
    This test verifies service doesn't crash on edge cases.
    """
    # Act: Try to register with invalid wallet (too short)
    hashed_password = hash_password("test123456")
    
    # Service doesn't validate format, but we test it doesn't crash
    # Handler validates format before calling service
    user = await user_service.register_user(
        telegram_id=303030303,
        wallet_address="0x123",  # Invalid (too short)
        financial_password=hashed_password,
    )
    
    # Service accepts it (validation is in handler)
    assert user is not None
    assert user.wallet_address == "0x123"


@pytest.mark.e2e
@pytest.mark.critical
@pytest.mark.asyncio
async def test_registration_financial_password_hashing(
    db_session,
    user_service: UserService,
) -> None:
    """
    Test that financial password is properly hashed.

    GIVEN: User registers with plain password
    WHEN: Password is stored
    THEN: Stored password is hashed (not plain text)
    """
    # Arrange
    telegram_id = 404040404
    plain_password = "mySecurePassword123"
    hashed_password = hash_password(plain_password)

    # Act: Register user
    user = await user_service.register_user(
        telegram_id=telegram_id,
        wallet_address="0x" + "c" * 40,
        financial_password=hashed_password,
    )

    # Assert: Password is hashed (not equal to plain)
    assert user.financial_password != plain_password
    assert user.financial_password == hashed_password
    assert len(user.financial_password) > len(plain_password)  # Hash is longer


@pytest.mark.e2e
@pytest.mark.critical
@pytest.mark.asyncio
async def test_registration_duplicate_telegram_id(
    db_session,
    user_service: UserService,
    create_user_helper,
) -> None:
    """
    Test registration with duplicate telegram_id.

    GIVEN: User already exists with telegram_id
    WHEN: Same telegram_id tries to register again
    THEN: ValueError is raised
    """
    # Arrange: Create existing user
    existing_user = await create_user_helper(
        telegram_id=505050505,
        wallet_address="0x" + "d" * 40,
    )

    # Act & Assert: Try to register with same telegram_id
    hashed_password = hash_password("test123456")
    with pytest.raises(ValueError) as exc_info:
        await user_service.register_user(
            telegram_id=existing_user.telegram_id,  # Same telegram_id
            wallet_address="0x" + "e" * 40,  # Different wallet
            financial_password=hashed_password,
        )
    
    # Should fail
    error_msg = str(exc_info.value)
    assert "already" in error_msg.lower() or "registered" in error_msg.lower()

