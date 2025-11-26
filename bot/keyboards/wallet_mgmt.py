"""
Wallet Management Keyboards (Reply).
"""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def wallet_dashboard_keyboard() -> ReplyKeyboardMarkup:
    """
    Main wallet dashboard keyboard.
    """
    builder = ReplyKeyboardBuilder()
    
    # Row 1: Send / Receive
    builder.row(
        KeyboardButton(text="📤 Отправить"),
        KeyboardButton(text="📥 Получить"),
    )
    
    # Row 2: Setup Keys/Addresses (Old capabilities)
    builder.row(
        KeyboardButton(text="📥 Настроить кошелек для входа"),
        KeyboardButton(text="📤 Настроить кошелек для выдачи"),
    )
    
    # Row 3: Refresh / Admin Panel
    builder.row(
        KeyboardButton(text="🔄 Обновить баланс"),
        KeyboardButton(text="👑 Админ-панель"),
    )
    
    return builder.as_markup(resize_keyboard=True)


def wallet_currency_selection_keyboard() -> ReplyKeyboardMarkup:
    """
    Currency selection for sending.
    """
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="🔶 BNB (Native)"),
        KeyboardButton(text="💵 USDT (BEP-20)"),
    )
    
    builder.row(
        KeyboardButton(text="◀️ Назад к кошельку"),
    )
    
    return builder.as_markup(resize_keyboard=True)


def wallet_amount_keyboard() -> ReplyKeyboardMarkup:
    """
    Quick amount selection.
    """
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="25%"),
        KeyboardButton(text="50%"),
        KeyboardButton(text="MAX"),
    )
    
    builder.row(
        KeyboardButton(text="❌ Отмена"),
    )
    
    return builder.as_markup(resize_keyboard=True)


def wallet_confirm_keyboard() -> ReplyKeyboardMarkup:
    """
    Transaction confirmation.
    """
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="✅ Подтвердить отправку"),
    )
    
    builder.row(
        KeyboardButton(text="❌ Отменить"),
    )
    
    return builder.as_markup(resize_keyboard=True)


def wallet_back_keyboard() -> ReplyKeyboardMarkup:
    """
    Simple back button.
    """
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="◀️ Назад к кошельку"),
    )
    return builder.as_markup(resize_keyboard=True)
