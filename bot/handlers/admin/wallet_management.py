"""
Admin Wallet Management Handler.

Provides "Trust Wallet"-like dashboard for system wallets using Reply Keyboards.
"""

from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

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

router = Router(name="admin_wallet_management")


@router.message(F.text == "🔐 Управление кошельком")
async def show_wallet_dashboard(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show main wallet dashboard."""
    # Clear previous state but keep admin token
    await clear_state_preserve_admin_token(state)
    await _show_dashboard(message, state)


async def _show_dashboard(message: Message, state: FSMContext) -> None:
    """Render the wallet dashboard."""
    await state.set_state(WalletManagementStates.menu)
    
    bs = get_blockchain_service()
    if not bs:
        await message.answer("❌ Сервис блокчейна недоступен.")
        return
    
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
    def fmt_bnb(val):
        return f"{val:.5f}" if val is not None else "Err"

    def fmt_usdt(val):
        return f"{val:.4f}" if val is not None else "Err"

    text = (
        "🔐 **Админ-кошелек (Dashboard)**\n\n"
        "🔥 **HOT WALLET (Выплатной)**\n"
        f"Адрес: `{hot_address}`\n"
        f"🔶 BNB: **{fmt_bnb(hot_bnb_bal)}**\n"
        f"💵 USDT: **{fmt_usdt(hot_usdt_bal)}**\n"
    )
    
    if has_cold:
        text += (
            "\n❄️ **INPUT WALLET (Приемный)**\n"
            f"Адрес: `{cold_address}`\n"
            f"🔶 BNB: **{fmt_bnb(cold_bnb_bal)}**\n"
            f"💵 USDT: **{fmt_usdt(cold_usdt_bal)}**\n"
            "_(Только просмотр, ключи не хранятся)_\n"
        )
        
    text += "\n👇 Выберите действие:"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=wallet_dashboard_keyboard()
    )


@router.message(F.text == "🔄 Обновить баланс", WalletManagementStates.menu)
async def refresh_dashboard(message: Message, state: FSMContext):
    """Refresh balances."""
    await message.answer("🔄 Обновляю балансы...")
    await _show_dashboard(message, state)


@router.message(F.text == "◀️ Назад к кошельку")
async def back_to_dashboard(message: Message, state: FSMContext):
    """Back to main dashboard."""
    await _show_dashboard(message, state)


@router.message(F.text == "📥 Получить", WalletManagementStates.menu)
async def show_receive_info(message: Message):
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
        
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=wallet_back_keyboard()
    )


@router.message(F.text == "⚙️ Настройки", WalletManagementStates.menu)
async def go_to_settings(message: Message, state: FSMContext, **data: Any):
    """Go to wallet settings (Backward compatibility but now integrated)."""
    from bot.handlers.admin.wallet_key_setup import handle_wallet_menu
    await handle_wallet_menu(message, state, **data)


@router.message(F.text == "📥 Настроить кошелек для входа", WalletManagementStates.menu)
async def dashboard_input_wallet_setup(message: Message, state: FSMContext, **data: Any):
    """Start input wallet setup from dashboard."""
    from bot.handlers.admin.wallet_key_setup import start_input_wallet_setup
    # We need to clear current state first to allow wallet setup state
    await state.set_state(None)
    await start_input_wallet_setup(message, state, **data)


@router.message(F.text == "📤 Настроить кошелек для выдачи", WalletManagementStates.menu)
async def dashboard_output_wallet_setup(message: Message, state: FSMContext, **data: Any):
    """Start output wallet setup from dashboard."""
    from bot.handlers.admin.wallet_key_setup import start_output_wallet_setup
    # We need to clear current state first to allow wallet setup state
    await state.set_state(None)
    await start_output_wallet_setup(message, state, **data)


# --- SEND FLOW ---

@router.message(F.text == "📤 Отправить", WalletManagementStates.menu)
async def start_send_flow(message: Message, state: FSMContext):
    """Start sending process."""
    await state.set_state(WalletManagementStates.selecting_currency_to_send)
    await message.answer(
        "📤 **Отправка средств (Hot Wallet)**\n\n"
        "Выберите валюту для отправки:",
        parse_mode="Markdown",
        reply_markup=wallet_currency_selection_keyboard()
    )


@router.message(WalletManagementStates.selecting_currency_to_send)
async def select_currency(message: Message, state: FSMContext):
    """Handle currency selection."""
    if message.text not in ["🔶 BNB (Native)", "💵 USDT (BEP-20)"]:
        if message.text == "◀️ Назад к кошельку":
            await back_to_dashboard(message, state)
            return
        await message.answer("❌ Выберите валюту из меню:")
        return

    currency = "BNB" if "BNB" in message.text else "USDT"
    await state.update_data(send_currency=currency)
    await state.set_state(WalletManagementStates.input_address_to_send)
    
    await message.answer(
        f"📤 **Отправка {currency}**\n\n"
        "Введите адрес получателя (BSC/BEP-20):",
        parse_mode="Markdown",
        reply_markup=wallet_back_keyboard()
    )


@router.message(WalletManagementStates.input_address_to_send)
async def input_address(message: Message, state: FSMContext):
    """Handle address input."""
    if message.text == "◀️ Назад к кошельку":
        await back_to_dashboard(message, state)
        return

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


@router.message(WalletManagementStates.input_amount_to_send)
async def process_amount_input(message: Message, state: FSMContext):
    """Handle amount input (text or percentage buttons)."""
    if message.text == "❌ Отмена":
        await back_to_dashboard(message, state)
        return

    bs = get_blockchain_service()
    data = await state.get_data()
    currency = data["send_currency"]
    
    amount = None
    
    # Handle Percentage Buttons
    if message.text in ["25%", "50%", "MAX"]:
        # Get balance
        if currency == "BNB":
            balance = await bs.get_native_balance(bs.wallet_address)
        else:
            balance = await bs.get_usdt_balance(bs.wallet_address)
            
        if not balance:
            await message.answer("❌ Ошибка получения баланса")
            return

        percent_map = {"25%": 25, "50%": 50, "MAX": 100}
        percent = percent_map[message.text]
        
        # Calculate amount
        amount = balance * Decimal(percent) / Decimal(100)
        
        # Leave some dust for gas if BNB and MAX
        if currency == "BNB" and percent == 100:
            amount = amount - Decimal("0.002") # Safety margin
            if amount < 0: amount = Decimal(0)
            
    else:
        # Handle Manual Input
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
    
    await message.answer(text, parse_mode="Markdown", reply_markup=wallet_confirm_keyboard())


@router.message(F.text == "✅ Подтвердить отправку", WalletManagementStates.confirm_transaction)
async def execute_transaction(message: Message, state: FSMContext):
    """Execute the transaction."""
    data = await state.get_data()
    currency = data["send_currency"]
    address = data["send_address"]
    amount = float(data["send_amount"])
    
    await message.answer("⏳ **Отправка транзакции...**\nОжидайте подтверждения сети.")
    
    bs = get_blockchain_service()
    
    try:
        if currency == "BNB":
            result = await bs.send_native_token(address, amount)
        else:
            result = await bs.send_payment(address, amount)
            
        if result["success"]:
            await message.answer(
                f"✅ **Транзакция отправлена!**\n\n"
                f"🔗 Hash: `{result['tx_hash']}`\n\n"
                f"[Посмотреть в Explorer](https://bscscan.com/tx/{result['tx_hash']})",
                parse_mode="Markdown",
                disable_web_page_preview=True,
                reply_markup=wallet_back_keyboard()
            )
        else:
            await message.answer(
                f"❌ **Ошибка отправки**\n\n"
                f"Причина: {result['error']}",
                reply_markup=wallet_back_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Wallet send error: {e}")
        await message.answer(
            f"❌ **Критическая ошибка**\n{str(e)}",
            reply_markup=wallet_back_keyboard()
        )


@router.message(F.text == "❌ Отменить", WalletManagementStates.confirm_transaction)
async def cancel_send(message: Message, state: FSMContext):
    """Cancel sending."""
    await _show_dashboard(message, state)
