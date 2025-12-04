"""
Keyboards.

Telegram keyboards (reply and inline).
"""

from bot.keyboards.reply import (
    main_menu_reply_keyboard,
    support_keyboard as support_reply_keyboard,
)
from bot.keyboards.inline import (
    admin_blockchain_keyboard,
    finpass_recovery_actions_keyboard,
)

__all__ = [
    # Reply keyboards
    "main_menu_reply_keyboard",
    "support_reply_keyboard",
    # Inline keyboards
    "admin_blockchain_keyboard",
    "finpass_recovery_actions_keyboard",
]
