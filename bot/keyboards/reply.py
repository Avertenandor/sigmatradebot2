"""
Reply keyboards.

Reply keyboard builders for main navigation.
"""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from loguru import logger

from app.models.blacklist import Blacklist, BlacklistActionType
from app.models.user import User


def main_menu_reply_keyboard(
    user: User | None = None,
    blacklist_entry: Blacklist | None = None,
    is_admin: bool = False,
) -> ReplyKeyboardMarkup:
    """
    Main menu reply keyboard.

    Conditionally shows buttons based on user status (e.g., blocked, admin).

    Args:
        user: The current user object (optional).
        blacklist_entry: The user's blacklist entry, if any (optional).
        is_admin: Whether the user is an admin (optional).

    Returns:
        ReplyKeyboardMarkup with main menu buttons
    """
    user_id = user.id if user else None
    telegram_id = user.telegram_id if user else None
    logger.info(
        f"[KEYBOARD] main_menu_reply_keyboard called: "
        f"user_id={user_id}, telegram_id={telegram_id}, "
        f"is_admin={is_admin}, "
        f"blacklist_active={blacklist_entry.is_active if blacklist_entry else False}"
    )

    builder = ReplyKeyboardBuilder()

    # If user is blocked (with appeal option), show only appeal button
    if (
        user
        and blacklist_entry
        and blacklist_entry.is_active
        and blacklist_entry.action_type == BlacklistActionType.BLOCKED
    ):
        logger.info(f"[KEYBOARD] User {telegram_id} is blocked, showing appeal button only")
        builder.row(
            KeyboardButton(text="📝 Подать апелляцию"),
        )
    else:
        # Standard menu for active users
        logger.info(f"[KEYBOARD] Building standard menu for user {telegram_id}")
        builder.row(
            KeyboardButton(text="💰 Депозит"),
            KeyboardButton(text="💸 Вывод"),
        )
        builder.row(
            KeyboardButton(text="👥 Рефералы"),
            KeyboardButton(text="📊 Баланс"),
        )
        builder.row(
            KeyboardButton(text="💬 Поддержка"),
            KeyboardButton(text="⚙️ Настройки"),
        )
        builder.row(
            KeyboardButton(text="📖 Инструкции"),
            KeyboardButton(text="📜 История"),
        )
        builder.row(
            KeyboardButton(text="✅ Пройти верификацию"),
        )

        # Add admin panel button for admins
        if is_admin:
            logger.info(f"[KEYBOARD] Adding admin panel button for user {telegram_id}")
            builder.row(
                KeyboardButton(text="👑 Админ-панель"),
            )
        else:
            logger.info(f"[KEYBOARD] NOT adding admin panel button (is_admin={is_admin}) for user {telegram_id}")

    keyboard = builder.as_markup(resize_keyboard=True)
    logger.info(f"[KEYBOARD] Keyboard created for user {telegram_id}, buttons count: {len(keyboard.keyboard)}")
    return keyboard


def support_keyboard() -> ReplyKeyboardMarkup:
    """
    Support menu reply keyboard.

    Returns:
        ReplyKeyboardMarkup with support options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="✉️ Создать обращение"),
    )
    builder.row(
        KeyboardButton(text="📋 Мои обращения"),
    )
    builder.row(
        KeyboardButton(text="❓ FAQ"),
    )
    # Покажем и "Назад", и явную кнопку выхода в главное меню —
    # пользователи привыкли к обоим вариантам.
    builder.row(
        KeyboardButton(text="⬅ Назад"),
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def deposit_keyboard() -> ReplyKeyboardMarkup:
    """
    Deposit menu reply keyboard.

    Returns:
        ReplyKeyboardMarkup with deposit options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="💰 Пополнить Level 1 (10 USDT)"),
    )
    builder.row(
        KeyboardButton(text="💰 Пополнить Level 2 (50 USDT)"),
    )
    builder.row(
        KeyboardButton(text="💰 Пополнить Level 3 (100 USDT)"),
    )
    builder.row(
        KeyboardButton(text="💰 Пополнить Level 4 (150 USDT)"),
    )
    builder.row(
        KeyboardButton(text="💰 Пополнить Level 5 (300 USDT)"),
    )
    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def withdrawal_keyboard() -> ReplyKeyboardMarkup:
    """
    Withdrawal menu reply keyboard.

    Returns:
        ReplyKeyboardMarkup with withdrawal options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="💸 Вывести всю сумму"),
    )
    builder.row(
        KeyboardButton(text="💵 Вывести указанную сумму"),
    )
    builder.row(
        KeyboardButton(text="📜 История выводов"),
    )
    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def referral_keyboard() -> ReplyKeyboardMarkup:
    """
    Referral menu reply keyboard.

    Returns:
        ReplyKeyboardMarkup with referral options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="👥 Мои рефералы"),
    )
    builder.row(
        KeyboardButton(text="💰 Мой заработок"),
    )
    builder.row(
        KeyboardButton(text="📊 Статистика рефералов"),
    )
    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def settings_keyboard() -> ReplyKeyboardMarkup:
    """
    Settings menu reply keyboard.

    Returns:
        ReplyKeyboardMarkup with settings options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="👤 Мой профиль"),
    )
    builder.row(
        KeyboardButton(text="💳 Мой кошелек"),
    )
    builder.row(
        KeyboardButton(text="🔔 Настройки уведомлений"),
    )
    builder.row(
        KeyboardButton(text="📝 Обновить контакты"),
    )
    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin panel reply keyboard.

    Returns:
        ReplyKeyboardMarkup with admin options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="📊 Статистика"),
    )
    builder.row(
        KeyboardButton(text="👥 Управление пользователями"),
    )
    builder.row(
        KeyboardButton(text="💸 Заявки на вывод"),
    )
    builder.row(
        KeyboardButton(text="📢 Рассылка"),
        KeyboardButton(text="🆘 Техподдержка"),
    )
    builder.row(
        KeyboardButton(text="🔐 Управление кошельком"),
    )
    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_users_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin users management keyboard.

    Returns:
        ReplyKeyboardMarkup with user management options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="🔍 Найти пользователя"),
    )
    builder.row(
        KeyboardButton(text="👥 Список пользователей"),
    )
    builder.row(
        KeyboardButton(text="🚫 Заблокировать пользователя"),
    )
    builder.row(
        KeyboardButton(text="⚠️ Терминировать аккаунт"),
    )
    builder.row(
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_withdrawals_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin withdrawals management keyboard.

    Returns:
        ReplyKeyboardMarkup with withdrawal management options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="⏳ Ожидающие выводы"),
    )
    builder.row(
        KeyboardButton(text="✅ Одобренные выводы"),
    )
    builder.row(
        KeyboardButton(text="❌ Отклоненные выводы"),
    )
    builder.row(
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def confirmation_keyboard() -> ReplyKeyboardMarkup:
    """
    Simple Yes/No confirmation keyboard.

    Returns:
        ReplyKeyboardMarkup with Yes/No options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="✅ Да"),
        KeyboardButton(text="❌ Нет"),
    )

    return builder.as_markup(resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Simple cancel keyboard.

    Returns:
        ReplyKeyboardMarkup with cancel option
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="❌ Отмена"),
    )

    return builder.as_markup(resize_keyboard=True)
