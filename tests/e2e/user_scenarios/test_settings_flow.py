"""
E2E tests for settings flow.

Tests complete settings scenarios:
- Notifications on/off (user_notification_settings)
- Change contacts (phone, email)
- Change language (i18n)
- Contact validation (phone format, email format)
"""

import pytest

from app.models.user_notification_settings import UserNotificationSettings
from app.repositories.user_notification_settings_repository import (
    UserNotificationSettingsRepository,
)
from app.services.user_notification_service import UserNotificationService
from app.services.user_service import UserService
from bot.i18n.loader import get_user_language, set_user_language
from tests.conftest import hash_password


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_notification_settings_toggle_deposit(
    db_session,
    user_notification_service: UserNotificationService,
    create_user_helper,
) -> None:
    """
    Test toggling deposit notifications.

    GIVEN: User with default notification settings
    WHEN: Toggles deposit notifications off
    THEN: Settings are updated
    """
    # Arrange: Create user
    user = await create_user_helper(
        telegram_id=111111111,
        wallet_address="0x" + "1" * 40,
    )

    # Get default settings
    settings = await user_notification_service.get_settings(user.id)
    initial_value = settings.deposit_notifications

    # Act: Toggle deposit notifications
    await user_notification_service.update_settings(
        user.id,
        deposit_notifications=not initial_value,
    )
    await db_session.commit()

    # Assert: Settings updated
    updated_settings = await user_notification_service.get_settings(user.id)
    assert updated_settings.deposit_notifications == (not initial_value)
    assert updated_settings.withdrawal_notifications == settings.withdrawal_notifications
    assert updated_settings.marketing_notifications == settings.marketing_notifications


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_notification_settings_toggle_withdrawal(
    db_session,
    user_notification_service: UserNotificationService,
    create_user_helper,
) -> None:
    """
    Test toggling withdrawal notifications.

    GIVEN: User with default notification settings
    WHEN: Toggles withdrawal notifications off
    THEN: Settings are updated
    """
    # Arrange: Create user
    user = await create_user_helper(
        telegram_id=222222222,
        wallet_address="0x" + "2" * 40,
    )

    # Get default settings
    settings = await user_notification_service.get_settings(user.id)
    initial_value = settings.withdrawal_notifications

    # Act: Toggle withdrawal notifications
    await user_notification_service.update_settings(
        user.id,
        withdrawal_notifications=not initial_value,
    )
    await db_session.commit()

    # Assert: Settings updated
    updated_settings = await user_notification_service.get_settings(user.id)
    assert updated_settings.withdrawal_notifications == (not initial_value)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_notification_settings_toggle_marketing(
    db_session,
    user_notification_service: UserNotificationService,
    create_user_helper,
) -> None:
    """
    Test toggling marketing notifications.

    GIVEN: User with default notification settings
    WHEN: Toggles marketing notifications on
    THEN: Settings are updated
    """
    # Arrange: Create user
    user = await create_user_helper(
        telegram_id=333333333,
        wallet_address="0x" + "3" * 40,
    )

    # Get default settings (marketing is False by default)
    settings = await user_notification_service.get_settings(user.id)
    assert settings.marketing_notifications is False

    # Act: Enable marketing notifications
    await user_notification_service.update_settings(
        user.id,
        marketing_notifications=True,
    )
    await db_session.commit()

    # Assert: Settings updated
    updated_settings = await user_notification_service.get_settings(user.id)
    assert updated_settings.marketing_notifications is True


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_change_contacts_phone(
    db_session,
    user_service: UserService,
    create_user_helper,
) -> None:
    """
    Test changing phone number.

    GIVEN: User with existing phone
    WHEN: Updates phone number
    THEN: Phone is updated in user profile
    """
    # Arrange: Create user with phone
    user = await create_user_helper(
        telegram_id=444444444,
        wallet_address="0x" + "4" * 40,
    )
    user.phone = "+1234567890"
    await db_session.commit()

    # Act: Update phone
    new_phone = "+9876543210"
    await user_service.update_profile(
        user.id,
        phone=new_phone,
    )

    # Assert: Phone updated
    await db_session.refresh(user)
    assert user.phone == new_phone


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_change_contacts_email(
    db_session,
    user_service: UserService,
    create_user_helper,
) -> None:
    """
    Test changing email.

    GIVEN: User with existing email
    WHEN: Updates email
    THEN: Email is updated in user profile
    """
    # Arrange: Create user with email
    user = await create_user_helper(
        telegram_id=555555555,
        wallet_address="0x" + "5" * 40,
    )
    user.email = "old@example.com"
    await db_session.commit()

    # Act: Update email
    new_email = "new@example.com"
    await user_service.update_profile(
        user.id,
        email=new_email,
    )

    # Assert: Email updated
    await db_session.refresh(user)
    assert user.email == new_email


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_change_language(
    db_session,
    create_user_helper,
) -> None:
    """
    Test changing language.

    GIVEN: User with default language (ru)
    WHEN: Changes language to en
    THEN: Language is updated
    """
    # Arrange: Create user
    user = await create_user_helper(
        telegram_id=666666666,
        wallet_address="0x" + "6" * 40,
    )

    # Get initial language (default is ru)
    initial_lang = await get_user_language(db_session, user.id)
    assert initial_lang == "ru"  # Default

    # Act: Change language to English
    success = await set_user_language(db_session, user.id, "en")

    # Assert: Language changed
    assert success is True
    new_lang = await get_user_language(db_session, user.id)
    assert new_lang == "en"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_contact_validation_phone_format(
    db_session,
    user_service: UserService,
    create_user_helper,
) -> None:
    """
    Test phone format validation.

    GIVEN: User
    WHEN: Updates phone with invalid format
    THEN: Validation should handle it (basic validation in handler)
    
    Note: Service doesn't validate format, handler does.
    This test verifies service accepts any string.
    """
    # Arrange: Create user
    user = await create_user_helper(
        telegram_id=777777777,
        wallet_address="0x" + "7" * 40,
    )

    # Act: Update with short phone (would fail in handler)
    # Service accepts it
    short_phone = "123"  # Too short
    await user_service.update_profile(
        user.id,
        phone=short_phone,
    )

    # Assert: Service accepts it (validation is in handler)
    await db_session.refresh(user)
    assert user.phone == short_phone


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_contact_validation_email_format(
    db_session,
    user_service: UserService,
    create_user_helper,
) -> None:
    """
    Test email format validation.

    GIVEN: User
    WHEN: Updates email with invalid format
    THEN: Validation should handle it (basic validation in handler)
    
    Note: Service doesn't validate format, handler does.
    This test verifies service accepts any string.
    """
    # Arrange: Create user
    user = await create_user_helper(
        telegram_id=888888888,
        wallet_address="0x" + "8" * 40,
    )

    # Act: Update with invalid email (would fail in handler)
    # Service accepts it
    invalid_email = "notanemail"  # No @
    await user_service.update_profile(
        user.id,
        email=invalid_email,
    )

    # Assert: Service accepts it (validation is in handler)
    await db_session.refresh(user)
    assert user.email == invalid_email


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_notification_settings_defaults(
    db_session,
    user_notification_service: UserNotificationService,
    create_user_helper,
) -> None:
    """
    Test default notification settings.

    GIVEN: New user
    WHEN: Gets notification settings
    THEN: Defaults are created (deposit=True, withdrawal=True, marketing=False)
    """
    # Arrange: Create user
    user = await create_user_helper(
        telegram_id=999999999,
        wallet_address="0x" + "9" * 40,
    )

    # Act: Get settings (creates defaults if not exist)
    settings = await user_notification_service.get_settings(user.id)

    # Assert: Defaults are correct
    assert settings.deposit_notifications is True
    assert settings.withdrawal_notifications is True
    assert settings.marketing_notifications is False
    assert settings.user_id == user.id

