"""
Wallet Management Keyboards.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def wallet_dashboard_keyboard(
    show_private_key: bool = False
) -> InlineKeyboardMarkup:
    """
    Main wallet dashboard keyboard.
    """
    builder = InlineKeyboardBuilder()
    
    # Row 1: Send / Receive
    builder.row(
        InlineKeyboardButton(text="📤 Отправить", callback_data="wallet_send_menu"),
        InlineKeyboardButton(text="📥 Получить", callback_data="wallet_receive"),
    )
    
    # Row 2: Refresh
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить баланс", callback_data="wallet_refresh"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="wallet_settings"),
    )
    
    return builder.as_markup()


def wallet_currency_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Currency selection for sending.
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔶 BNB (Native)", callback_data="wallet_send_bnb"),
        InlineKeyboardButton(text="💵 USDT (BEP-20)", callback_data="wallet_send_usdt"),
    )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="wallet_back_to_dashboard"),
    )
    
    return builder.as_markup()


def wallet_amount_keyboard() -> InlineKeyboardMarkup:
    """
    Quick amount selection.
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="25%", callback_data="wallet_amount_25"),
        InlineKeyboardButton(text="50%", callback_data="wallet_amount_50"),
        InlineKeyboardButton(text="MAX", callback_data="wallet_amount_100"),
    )
    
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="wallet_cancel_send"),
    )
    
    return builder.as_markup()


def wallet_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Transaction confirmation.
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить отправку", callback_data="wallet_confirm_tx"),
    )
    
    builder.row(
        InlineKeyboardButton(text="❌ Отменить", callback_data="wallet_cancel_send"),
    )
    
    return builder.as_markup()


def wallet_back_keyboard() -> InlineKeyboardMarkup:
    """
    Simple back button.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="wallet_back_to_dashboard"),
    )
    return builder.as_markup()

