"""
Admin Wallet Management Handler.

Provides "Trust Wallet"-like dashboard for system wallets.
"""

from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.services.blockchain_service import get_blockchain_service
from bot.keyboards.wallet_mgmt import (
    wallet_amount_keyboard,
    wallet_back_keyboard,
    wallet_confirm_keyboard,
    wallet_currency_selection_keyboard,
    wallet_dashboard_keyboard,
)
from bot.states.wallet_management import WalletManagementStates
from bot.utils.admin_utils import clear_state_preserve_admin_token
from bot.utils.formatters import format_usdt

router = Router(name="admin_wallet_management")


@router.message(F.text == "🔐 Управление кошельком")
async def show_wallet_dashboard(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show main wallet dashboard."""
    await _show_dashboard(message, state)


async def _show_dashboard(message: Message, state: FSMContext, edit_mode: bool = False) -> None:
    """Render the wallet dashboard."""
    await state.set_state(WalletManagementStates.menu)
    
    bs = get_blockchain_service()
    
    # Hot Wallet (Output)
    hot_address = bs.wallet_address
    hot_bnb_bal = await bs.get_native_balance(hot_address)
    hot_usdt_bal = await bs.get_usdt_balance(hot_address)
    
    # System Wallet (Input/Cold) - if configured different from Hot
    cold_address = bs.system_wallet_address
    cold_bnb_bal = Decimal("0")
    cold_usdt_bal = Decimal("0")
    
    has_cold = cold_address and cold_address.lower() != hot_address.lower()
    
    if has_cold:
        cold_bnb_bal = await bs.get_native_balance(cold_address) or Decimal("0")
        cold_usdt_bal = await bs.get_usdt_balance(cold_address) or Decimal("0")

    # Formatting
    def fmt(val):
        return f"{val:.4f}" if val is not None else "Err"

    text = (
        "🔐 **Админ-кошелек (Dashboard)**\n\n"
        "🔥 **HOT WALLET (Выплатной)**\n"
        f"Адрес: `{hot_address}`\n"
        f"🔶 BNB: **{fmt(hot_bnb_bal)}**\n"
        f"💵 USDT: **{fmt(hot_usdt_bal)}**\n"
    )
    
    if has_cold:
        text += (
            "\n❄️ **INPUT WALLET (Приемный)**\n"
            f"Адрес: `{cold_address}`\n"
            f"🔶 BNB: **{fmt(cold_bnb_bal)}**\n"
            f"💵 USDT: **{fmt(cold_usdt_bal)}**\n"
            "_(Только просмотр, ключи не хранятся)_\n"
        )
        
    text += "\n👇 Выберите действие:"

    if edit_mode:
        await message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=wallet_dashboard_keyboard()
        )
    else:
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=wallet_dashboard_keyboard()
        )


@router.callback_query(F.data == "wallet_refresh")
async def refresh_dashboard(callback: CallbackQuery, state: FSMContext):
    """Refresh balances."""
    await callback.answer("🔄 Обновляю балансы...")
    await _show_dashboard(callback.message, state, edit_mode=True)


@router.callback_query(F.data == "wallet_back_to_dashboard")
async def back_to_dashboard(callback: CallbackQuery, state: FSMContext):
    """Back to main dashboard."""
    await _show_dashboard(callback.message, state, edit_mode=True)


@router.callback_query(F.data == "wallet_settings")
async def go_to_settings(callback: CallbackQuery, state: FSMContext, **data: Any):
    """Go to wallet settings (Reply Keyboard)."""
    from bot.handlers.admin.wallet_key_setup import handle_wallet_menu
    
    await callback.answer()
    # Call setup menu (which uses Reply Keyboard)
    await handle_wallet_menu(callback.message, state, **data)


@router.callback_query(F.data == "wallet_receive")
async def show_receive_info(callback: CallbackQuery):
    """Show receive addresses."""
    bs = get_blockchain_service()
    hot_address = bs.wallet_address
    cold_address = bs.system_wallet_address
    
    text = (
        "📥 **Получение средств**\n\n"
        "🔥 **Hot Wallet (Для пополнения газа):**\n"
        f"`{hot_address}`\n\n"
    )
    
    if cold_address and cold_address.lower() != hot_address.lower():
        text += (
            "❄️ **Input Wallet (Для депозитов):**\n"
            f"`{cold_address}`\n"
        )
        
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=wallet_back_keyboard()
    )


# --- SEND FLOW ---

@router.callback_query(F.data == "wallet_send_menu")
async def start_send_flow(callback: CallbackQuery, state: FSMContext):
    """Start sending process."""
    await state.set_state(WalletManagementStates.selecting_currency_to_send)
    await callback.message.edit_text(
        "📤 **Отправка средств (Hot Wallet)**\n\n"
        "Выберите валюту для отправки:",
        parse_mode="Markdown",
        reply_markup=wallet_currency_selection_keyboard()
    )


@router.callback_query(F.data.startswith("wallet_send_"))
async def select_currency(callback: CallbackQuery, state: FSMContext):
    """Handle currency selection."""
    currency = callback.data.split("_")[2].upper()  # BNB or USDT
    await state.update_data(send_currency=currency)
    await state.set_state(WalletManagementStates.input_address_to_send)
    
    await callback.message.edit_text(
        f"📤 **Отправка {currency}**\n\n"
        "Введите адрес получателя (BSC/BEP-20):",
        parse_mode="Markdown",
        reply_markup=wallet_back_keyboard()
    )


@router.message(WalletManagementStates.input_address_to_send)
async def input_address(message: Message, state: FSMContext):
    """Handle address input."""
    address = message.text.strip()
    bs = get_blockchain_service()
    
    if not await bs.validate_wallet_address(address):
        await message.answer(
            "❌ Неверный формат адреса. Попробуйте еще раз:",
            reply_markup=wallet_back_keyboard()
        )
        return

    await state.update_data(send_address=address)
    data = await state.get_data()
    currency = data["send_currency"]
    
    await state.set_state(WalletManagementStates.input_amount_to_send)
    await message.answer(
        f"📤 **Отправка {currency}**\n"
        f"Получатель: `{address}`\n\n"
        "Введите сумму или выберите %:",
        parse_mode="Markdown",
        reply_markup=wallet_amount_keyboard()
    )


@router.callback_query(F.data.startswith("wallet_amount_"))
async def select_amount_percent(callback: CallbackQuery, state: FSMContext):
    """Handle percentage amount selection."""
    percent = int(callback.data.split("_")[2])
    bs = get_blockchain_service()
    data = await state.get_data()
    currency = data["send_currency"]
    
    # Get balance
    if currency == "BNB":
        balance = await bs.get_native_balance(bs.wallet_address)
    else:
        balance = await bs.get_usdt_balance(bs.wallet_address)
        
    if not balance:
        await callback.answer("❌ Ошибка получения баланса", show_alert=True)
        return

    # Calculate amount
    amount = balance * Decimal(percent) / Decimal(100)
    
    # Leave some dust for gas if BNB
    if currency == "BNB" and percent == 100:
        amount = amount - Decimal("0.002") # Safety margin
        if amount < 0: amount = Decimal(0)

    await state.update_data(send_amount=str(amount))
    await _show_confirmation(callback.message, state)


@router.message(WalletManagementStates.input_amount_to_send)
async def input_amount(message: Message, state: FSMContext):
    """Handle manual amount input."""
    try:
        amount = Decimal(message.text.replace(",", "."))
        if amount <= 0: raise ValueError
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите число.")
        return

    await state.update_data(send_amount=str(amount))
    await _show_confirmation(message, state)


async def _show_confirmation(message: Message, state: FSMContext):
    """Show transaction confirmation."""
    data = await state.get_data()
    currency = data["send_currency"]
    address = data["send_address"]
    amount = Decimal(data["send_amount"])
    
    await state.set_state(WalletManagementStates.confirm_transaction)
    
    text = (
        "📝 **Подтверждение транзакции**\n\n"
        f"💸 Сумма: **{amount} {currency}**\n"
        f"📬 Получатель: `{address}`\n"
        "📡 Сеть: BSC (Binance Smart Chain)\n\n"
        "Проверьте данные и подтвердите отправку."
    )
    
    # If called from message handler, answer. If from callback, edit.
    if isinstance(message, Message):
        await message.answer(text, parse_mode="Markdown", reply_markup=wallet_confirm_keyboard())
    else:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=wallet_confirm_keyboard())


@router.callback_query(F.data == "wallet_confirm_tx")
async def execute_transaction(callback: CallbackQuery, state: FSMContext):
    """Execute the transaction."""
    data = await state.get_data()
    currency = data["send_currency"]
    address = data["send_address"]
    amount = float(data["send_amount"])
    
    await callback.message.edit_text("⏳ **Отправка транзакции...**\nОжидайте подтверждения сети.")
    
    bs = get_blockchain_service()
    
    try:
        if currency == "BNB":
            result = await bs.send_native_token(address, amount)
        else:
            result = await bs.send_payment(address, amount)
            
        if result["success"]:
            await callback.message.edit_text(
                f"✅ **Транзакция отправлена!**\n\n"
                f"🔗 Hash: `{result['tx_hash']}`\n\n"
                f"[Посмотреть в Explorer](https://bscscan.com/tx/{result['tx_hash']})",
                parse_mode="Markdown",
                disable_web_page_preview=True,
                reply_markup=wallet_back_keyboard()
            )
        else:
            await callback.message.edit_text(
                f"❌ **Ошибка отправки**\n\n"
                f"Причина: {result['error']}",
                reply_markup=wallet_back_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Wallet send error: {e}")
        await callback.message.edit_text(
            f"❌ **Критическая ошибка**\n{str(e)}",
            reply_markup=wallet_back_keyboard()
        )


@router.callback_query(F.data == "wallet_cancel_send")
async def cancel_send(callback: CallbackQuery, state: FSMContext):
    """Cancel sending."""
    await _show_dashboard(callback.message, state, edit_mode=True)

