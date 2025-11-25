"""
Inline keyboards.

Inline keyboard builders for interactive menus.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_blockchain_keyboard(
    active_provider: str,
    is_auto_switch: bool
) -> InlineKeyboardMarkup:
    """
    Keyboard for blockchain settings management.
    
    Args:
        active_provider: Currently active provider name ('quicknode' or 'nodereal')
        is_auto_switch: Whether auto-switch is enabled
        
    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()
    
    # Provider selection
    # We highlight the active one
    qn_text = "✅ QuickNode" if active_provider == "quicknode" else "QuickNode"
    nr_text = "✅ NodeReal" if active_provider == "nodereal" else "NodeReal"
    
    # Row 1: Providers
    builder.row(
        InlineKeyboardButton(text=qn_text, callback_data="blockchain_set_quicknode"),
        InlineKeyboardButton(text=nr_text, callback_data="blockchain_set_nodereal"),
    )
    
    # Row 2: Auto-switch toggle
    auto_text = "✅ Авто-смена ВКЛ" if is_auto_switch else "❌ Авто-смена ВЫКЛ"
    builder.row(
        InlineKeyboardButton(text=auto_text, callback_data="blockchain_toggle_auto")
    )
    
    # Row 3: Refresh
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить статус", callback_data="blockchain_refresh")
    )
    
    return builder.as_markup()

