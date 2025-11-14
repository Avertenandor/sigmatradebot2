"""
Main Keyboard
Main menu keyboard for the bot
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """
    Get main menu keyboard

    Args:
        is_admin: Whether the user is an admin

    Returns:
        Main menu keyboard
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="💰 Депозит", callback_data="deposit"
            ),
            InlineKeyboardButton(
                text="💸 Вывод", callback_data="withdrawal"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🤝 Рефералы", callback_data="referrals"
            ),
            InlineKeyboardButton(
                text="👤 Профиль", callback_data="profile"
            ),
        ],
        [
            InlineKeyboardButton(
                text="📊 История", callback_data="transaction_history"
            ),
            InlineKeyboardButton(
                text="🆘 Поддержка", callback_data="support"
            ),
        ],
    ]

    # Add admin panel button if user is admin
    if is_admin:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="👑 Админ-панель", callback_data="admin_panel"
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
