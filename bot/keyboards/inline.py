"""
Inline keyboards.

Inline keyboard builders for various bot functions.
"""

from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

if TYPE_CHECKING:
    from app.models.user_notification_settings import UserNotificationSettings


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Main menu keyboard.

    Returns:
        InlineKeyboardMarkup with main menu options
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="💰 Депозит", callback_data="menu:deposit"),
        InlineKeyboardButton(text="💸 Вывод", callback_data="menu:withdrawal"),
    )
    builder.row(
        InlineKeyboardButton(
            text="👥 Рефералы", callback_data="menu:referral"
        ),
        InlineKeyboardButton(text="📊 Баланс", callback_data="menu:balance"),
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Награды", callback_data="menu:rewards"),
        InlineKeyboardButton(text="📜 История", callback_data="menu:history"),
    )
    builder.row(
        InlineKeyboardButton(
            text="💬 Поддержка", callback_data="menu:support"
        ),
        InlineKeyboardButton(
            text="⚙️ Настройки", callback_data="menu:settings"
        ),
    )

    return builder.as_markup()


def deposit_keyboard() -> InlineKeyboardMarkup:
    """
    Deposit levels keyboard.

    Returns:
        InlineKeyboardMarkup with deposit level options
    """
    builder = InlineKeyboardBuilder()

    # Deposit levels (1-5)
    for level in range(1, 6):
        builder.row(
            InlineKeyboardButton(
                text=f"📦 Уровень {level}",
                callback_data=f"deposit:level:{level}",
            )
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")
    )

    return builder.as_markup()


def withdrawal_keyboard() -> InlineKeyboardMarkup:
    """
    Withdrawal keyboard.

    Returns:
        InlineKeyboardMarkup with withdrawal options
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="💸 Вывести все", callback_data="withdrawal:all"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💵 Вывести сумму", callback_data="withdrawal:amount"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📜 История выводов", callback_data="withdrawal:history"
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")
    )

    return builder.as_markup()


def referral_keyboard(user_telegram_id: int) -> InlineKeyboardMarkup:
    """
    Referral keyboard.

    Args:
        user_telegram_id: User's Telegram ID for referral link

    Returns:
        InlineKeyboardMarkup with referral options
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="👥 Мои рефералы", callback_data="referral:list"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💰 Заработок", callback_data="referral:earnings"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика", callback_data="referral:stats"
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")
    )

    return builder.as_markup()


def support_keyboard() -> InlineKeyboardMarkup:
    """
    Support keyboard.

    Returns:
        InlineKeyboardMarkup with support options
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✉️ Создать обращение",
            callback_data="support:create",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 Мои обращения",
            callback_data="support:list",
        )
    )
    builder.row(
        InlineKeyboardButton(text="❓ FAQ", callback_data="support:faq")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")
    )

    return builder.as_markup()


def admin_keyboard() -> InlineKeyboardMarkup:
    """
    Admin panel keyboard.

    Returns:
        InlineKeyboardMarkup with admin options
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="👥 Пользователи", callback_data="admin:users"
        ),
        InlineKeyboardButton(
            text="💰 Депозиты", callback_data="admin:deposits"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="💸 Выводы", callback_data="admin:withdrawals"
        ),
        InlineKeyboardButton(text="🎁 Награды", callback_data="admin:rewards"),
    )
    builder.row(
        InlineKeyboardButton(
            text="💬 Поддержка", callback_data="admin:support"
        ),
        InlineKeyboardButton(
            text="📊 Статистика", callback_data="admin:stats"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="⚙️ Настройки", callback_data="admin:settings"
        )
    )

    return builder.as_markup()


def settings_keyboard() -> InlineKeyboardMarkup:
    """
    User settings keyboard.

    Returns:
        InlineKeyboardMarkup with settings options
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="👤 Профиль", callback_data="settings:profile"
        ),
        InlineKeyboardButton(
            text="💳 Кошелек", callback_data="settings:wallet"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🔔 Уведомления", callback_data="settings:notifications"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📝 Обновить контакты",
            callback_data="settings:update_contacts",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="✅ Пройти верификацию", callback_data="verification:start"
        ),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main"),
    )

    return builder.as_markup()


def notification_settings_keyboard(
    settings: "UserNotificationSettings",
) -> InlineKeyboardMarkup:
    """
    Notification settings keyboard.

    Args:
        settings: UserNotificationSettings instance

    Returns:
        InlineKeyboardMarkup with notification toggle buttons
    """
    builder = InlineKeyboardBuilder()

    # Deposit notifications toggle
    deposit_text = (
        "✅ Уведомления о депозитах" if settings.deposit_notifications
        else "❌ Уведомления о депозитах"
    )
    builder.row(
        InlineKeyboardButton(
            text=deposit_text,
            callback_data="toggle_notification_deposit"
        )
    )

    # Withdrawal notifications toggle
    withdrawal_text = (
        "✅ Уведомления о выводах" if settings.withdrawal_notifications
        else "❌ Уведомления о выводах"
    )
    builder.row(
        InlineKeyboardButton(
            text=withdrawal_text,
            callback_data="toggle_notification_withdrawal"
        )
    )

    # Marketing notifications toggle
    marketing_text = (
        "✅ Маркетинговые уведомления" if settings.marketing_notifications
        else "❌ Маркетинговые уведомления"
    )
    builder.row(
        InlineKeyboardButton(
            text=marketing_text,
            callback_data="toggle_notification_marketing"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад к настройкам",
            callback_data="menu:settings"
        )
    )

    return builder.as_markup()
