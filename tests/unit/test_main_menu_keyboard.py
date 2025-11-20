"""
Unit tests for main menu reply keyboard.

Tests that main_menu_reply_keyboard() correctly shows buttons
based on user role, blacklist status, and admin privileges.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blacklist import Blacklist, BlacklistActionType
from app.models.user import User
from app.repositories.blacklist_repository import BlacklistRepository
from app.repositories.user_repository import UserRepository
from bot.keyboards.reply import main_menu_reply_keyboard


def extract_button_texts(keyboard) -> list[str]:
    """
    Extract all button texts from keyboard.

    Args:
        keyboard: ReplyKeyboardMarkup instance

    Returns:
        List of button text strings
    """
    buttons = []
    for row in keyboard.keyboard:
        for button in row:
            buttons.append(button.text)
    return buttons


@pytest.mark.unit
def test_guest_menu_buttons() -> None:
    """
    Test that guest (user=None) sees only basic buttons.

    Expected buttons:
    - 📖 Инструкции
    - 💬 Поддержка
    - 📝 Регистрация

    Should NOT have:
    - Депозит, Вывод, Админ-панель
    """
    keyboard = main_menu_reply_keyboard(user=None, blacklist_entry=None, is_admin=False)
    buttons = extract_button_texts(keyboard)

    # Should have these
    assert "📖 Инструкции" in buttons
    assert "💬 Поддержка" in buttons
    assert "📝 Регистрация" in buttons

    # Should NOT have these
    assert "💰 Депозит" not in buttons
    assert "💸 Вывод" not in buttons
    assert "👑 Админ-панель" not in buttons
    assert "📦 Мои депозиты" not in buttons

    # Should have exactly 3 buttons
    assert len(buttons) == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verified_user_menu_buttons(
    db_session: AsyncSession,
) -> None:
    """
    Test that verified user sees all main buttons but NO admin panel.

    Expected buttons:
    - Все основные кнопки (депозиты, выводы, рефералы и т.д.)
    - НЕТ админ-панели (is_admin=False)
    """
    # Create verified user
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=111111111,
        wallet_address="0x1111111111111111111111111111111111111111",
        financial_password_hash="test_hash",
    )
    user.is_verified = True
    await db_session.commit()

    keyboard = main_menu_reply_keyboard(
        user=user, blacklist_entry=None, is_admin=False
    )
    buttons = extract_button_texts(keyboard)

    # Should have all main buttons
    assert "💰 Депозит" in buttons
    assert "💸 Вывод" in buttons
    assert "📦 Мои депозиты" in buttons
    assert "👥 Рефералы" in buttons
    assert "📊 Баланс" in buttons
    assert "💬 Поддержка" in buttons
    assert "⚙️ Настройки" in buttons
    assert "📖 Инструкции" in buttons
    assert "📜 История" in buttons
    assert "🔑 Восстановить финпароль" in buttons

    # Should NOT have verification button (already verified)
    assert "✅ Пройти верификацию" not in buttons

    # Should NOT have admin panel
    assert "👑 Админ-панель" not in buttons

    # Should NOT have registration (already registered)
    assert "📝 Регистрация" not in buttons


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unverified_user_menu_buttons(
    db_session: AsyncSession,
) -> None:
    """
    Test that unverified user sees verification button.

    Expected buttons:
    - Все основные кнопки
    - ✅ Пройти верификацию (is_verified=False)
    - НЕТ админ-панели
    """
    # Create unverified user
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=222222222,
        wallet_address="0x2222222222222222222222222222222222222222",
        financial_password_hash="test_hash",
    )
    user.is_verified = False
    await db_session.commit()

    keyboard = main_menu_reply_keyboard(
        user=user, blacklist_entry=None, is_admin=False
    )
    buttons = extract_button_texts(keyboard)

    # Should have verification button
    assert "✅ Пройти верификацию" in buttons

    # Should NOT have admin panel
    assert "👑 Админ-панель" not in buttons


@pytest.mark.unit
@pytest.mark.asyncio
async def test_blocked_user_menu(
    db_session: AsyncSession,
) -> None:
    """
    Test that BLOCKED user sees ONLY appeal button.

    Expected buttons:
    - ТОЛЬКО "📝 Подать апелляцию"

    Should NOT have:
    - Все остальные кнопки
    """
    # Create user
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=333333333,
        wallet_address="0x3333333333333333333333333333333333333333",
        financial_password_hash="test_hash",
    )
    await db_session.commit()

    # Create BLOCKED blacklist entry
    blacklist_repo = BlacklistRepository(db_session)
    blacklist_entry = await blacklist_repo.create(
        telegram_id=user.telegram_id,
        action_type=BlacklistActionType.BLOCKED,
        reason="Test block",
        is_active=True,
    )
    await db_session.commit()

    keyboard = main_menu_reply_keyboard(
        user=user, blacklist_entry=blacklist_entry, is_admin=False
    )
    buttons = extract_button_texts(keyboard)

    # Should have ONLY appeal button
    assert "📝 Подать апелляцию" in buttons
    assert len(buttons) == 1

    # Should NOT have any other buttons
    assert "💰 Депозит" not in buttons
    assert "💸 Вывод" not in buttons
    assert "👑 Админ-панель" not in buttons
    assert "📖 Инструкции" not in buttons


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_menu_has_admin_panel(
    db_session: AsyncSession,
) -> None:
    """
    Test that admin user sees admin panel button.

    Expected buttons:
    - Все обычные кнопки
    - "👑 Админ-панель" (is_admin=True)
    """
    # Create user
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=444444444,
        wallet_address="0x4444444444444444444444444444444444444444",
        financial_password_hash="test_hash",
    )
    user.is_verified = True
    await db_session.commit()

    keyboard = main_menu_reply_keyboard(
        user=user, blacklist_entry=None, is_admin=True
    )
    buttons = extract_button_texts(keyboard)

    # Should have admin panel
    assert "👑 Админ-панель" in buttons

    # Should also have all regular buttons
    assert "💰 Депозит" in buttons
    assert "💸 Вывод" in buttons
    assert "📦 Мои депозиты" in buttons


@pytest.mark.unit
@pytest.mark.asyncio
async def test_non_admin_no_admin_panel(
    db_session: AsyncSession,
) -> None:
    """
    Test that regular user with is_admin=False does NOT see admin panel.

    Expected buttons:
    - Все обычные кнопки
    - НЕТ "👑 Админ-панель"
    """
    # Create user
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=555555555,
        wallet_address="0x5555555555555555555555555555555555555555",
        financial_password_hash="test_hash",
    )
    user.is_verified = True
    await db_session.commit()

    keyboard = main_menu_reply_keyboard(
        user=user, blacklist_entry=None, is_admin=False
    )
    buttons = extract_button_texts(keyboard)

    # Should NOT have admin panel
    assert "👑 Админ-панель" not in buttons

    # Should have regular buttons
    assert "💰 Депозит" in buttons
    assert "💸 Вывод" in buttons


@pytest.mark.unit
@pytest.mark.asyncio
async def test_blocked_admin_no_admin_panel(
    db_session: AsyncSession,
) -> None:
    """
    Test that BLOCKED admin does NOT see admin panel (only appeal).

    Expected buttons:
    - ТОЛЬКО "📝 Подать апелляцию"
    - НЕТ админ-панели (блокировка имеет приоритет)
    """
    # Create user
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=666666666,
        wallet_address="0x6666666666666666666666666666666666666666",
        financial_password_hash="test_hash",
    )
    await db_session.commit()

    # Create BLOCKED blacklist entry
    blacklist_repo = BlacklistRepository(db_session)
    blacklist_entry = await blacklist_repo.create(
        telegram_id=user.telegram_id,
        action_type=BlacklistActionType.BLOCKED,
        reason="Blocked admin",
        is_active=True,
    )
    await db_session.commit()

    # Even if is_admin=True, BLOCKED status should override
    keyboard = main_menu_reply_keyboard(
        user=user, blacklist_entry=blacklist_entry, is_admin=True
    )
    buttons = extract_button_texts(keyboard)

    # Should have ONLY appeal button
    assert "📝 Подать апелляцию" in buttons
    assert len(buttons) == 1

    # Should NOT have admin panel (blocked status overrides)
    assert "👑 Админ-панель" not in buttons


@pytest.mark.unit
@pytest.mark.asyncio
async def test_inactive_blacklist_entry_ignored(
    db_session: AsyncSession,
) -> None:
    """
    Test that inactive blacklist entry does not affect menu.

    Expected buttons:
    - All regular buttons (blacklist entry is_active=False)
    """
    # Create user
    user_repo = UserRepository(db_session)
    user = await user_repo.create(
        telegram_id=777777777,
        wallet_address="0x7777777777777777777777777777777777777777",
        financial_password_hash="test_hash",
    )
    user.is_verified = True
    await db_session.commit()

    # Create INACTIVE BLOCKED blacklist entry
    blacklist_repo = BlacklistRepository(db_session)
    blacklist_entry = await blacklist_repo.create(
        telegram_id=user.telegram_id,
        action_type=BlacklistActionType.BLOCKED,
        reason="Old block (now inactive)",
        is_active=False,  # Inactive!
    )
    await db_session.commit()

    keyboard = main_menu_reply_keyboard(
        user=user, blacklist_entry=blacklist_entry, is_admin=False
    )
    buttons = extract_button_texts(keyboard)

    # Should have all regular buttons (inactive blacklist ignored)
    assert "💰 Депозит" in buttons
    assert "💸 Вывод" in buttons

    # Should NOT have appeal button (blacklist is inactive)
    assert "📝 Подать апелляцию" not in buttons

