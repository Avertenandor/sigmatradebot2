"""
Reply keyboards.

Reply keyboard builders for main navigation.
"""

from typing import Optional

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.models.blacklist import Blacklist
from app.models.blacklist import BlacklistActionType
from app.models.user import User


def main_menu_reply_keyboard(
    user: Optional[User] = None,
    blacklist_entry: Optional[Blacklist] = None,
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
    builder = ReplyKeyboardBuilder()

    # If user is blocked (with appeal option), show only appeal button
    if (
        user
        and blacklist_entry
        and blacklist_entry.is_active
        and blacklist_entry.action_type == BlacklistActionType.BLOCKED
    ):
        builder.row(
            KeyboardButton(text="📝 Подать апелляцию"),
        )
    else:
        # Standard menu for active users
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
            KeyboardButton(text="✅ Пройти верификацию"),
        )
        
        # Add admin panel button for admins
        if is_admin:
            builder.row(
                KeyboardButton(text="👑 Админ-панель"),
            )

    return builder.as_markup(resize_keyboard=True)


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
    builder.row(
        KeyboardButton(text="◀️ Назад"),
    )

    return builder.as_markup(resize_keyboard=True)
