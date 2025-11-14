"""
Referral Keyboards
Inline keyboards for referral program
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_referral_menu_keyboard() -> InlineKeyboardMarkup:
    """Get referral menu keyboard"""
    buttons = [
        [
            InlineKeyboardButton(
                text="🔗 Моя ссылка", callback_data="referral_link"
            ),
        ],
        [
            InlineKeyboardButton(
                text="📊 Уровень 1", callback_data="referral_stats_1"
            ),
            InlineKeyboardButton(
                text="📊 Уровень 2", callback_data="referral_stats_2"
            ),
            InlineKeyboardButton(
                text="📊 Уровень 3", callback_data="referral_stats_3"
            ),
        ],
        [
            InlineKeyboardButton(
                text="💸 Мои доходы", callback_data="referral_earnings_1"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🏆 Таблица лидеров",
                callback_data="referral_leaderboard",
            ),
        ],
        [
            InlineKeyboardButton(
                text="◀️ Главное меню", callback_data="main_menu"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_referral_stats_keyboard(level: int) -> InlineKeyboardMarkup:
    """Get referral stats keyboard with level navigation"""
    buttons = []

    # Level navigation
    level_buttons = []
    for i in range(1, 4):
        text = f"{'✅ ' if i == level else ''}Уровень {i}"
        level_buttons.append(
            InlineKeyboardButton(
                text=text, callback_data=f"referral_stats_{i}"
            )
        )
    buttons.append(level_buttons)

    # Back button
    buttons.append(
        [
            InlineKeyboardButton(
                text="◀️ Назад", callback_data="referrals"
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_referral_earnings_keyboard(
    page: int, total_pages: int
) -> InlineKeyboardMarkup:
    """Get referral earnings keyboard with pagination"""
    buttons = []

    # Pagination
    if page > 1 or page < total_pages:
        pagination_row = []
        if page > 1:
            pagination_row.append(
                InlineKeyboardButton(
                    text="◀️ Назад", callback_data=f"referral_earnings_{page - 1}"
                )
            )
        if page < total_pages:
            pagination_row.append(
                InlineKeyboardButton(
                    text="Вперёд ▶️",
                    callback_data=f"referral_earnings_{page + 1}",
                )
            )
        if pagination_row:
            buttons.append(pagination_row)

    # Back button
    buttons.append(
        [
            InlineKeyboardButton(
                text="◀️ К рефералам", callback_data="referrals"
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_button(callback_data: str) -> InlineKeyboardMarkup:
    """Get simple back button"""
    buttons = [
        [InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
