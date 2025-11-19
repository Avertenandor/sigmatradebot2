"""
Keyboards.

Telegram keyboards (reply only).
"""

from bot.keyboards.reply import (
    main_menu_reply_keyboard,
    support_keyboard as support_reply_keyboard,
)

__all__ = [
    # Reply keyboards
    "main_menu_reply_keyboard",
    "support_reply_keyboard",
]
