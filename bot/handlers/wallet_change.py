"""
Wallet change handlers.
"""

import re
from typing import Any

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.user_service import UserService
from bot.keyboards.reply import cancel_keyboard, main_menu_reply_keyboard, settings_keyboard
from bot.states.wallet_change import WalletChangeStates

router = Router(name="wallet_change")


@router.message(StateFilter('*'), F.text == "🔄 Сменить кошелек")
async def start_wallet_change(
    message: Message,
    state: FSMContext,
) -> None:
    """Start wallet change process."""
    await message.answer(
        "📝 *Смена кошелька*\n\n"
        "Введите новый адрес вашего BEP-20 кошелька.\n\n"
        "⚠️ **КРИТИЧНО:**\n"
        "• Указывайте только *ЛИЧНЫЙ* кошелек (Trust Wallet, MetaMask, SafePal или холодный кошелек)\n"
        "• 🚫 *НЕ указывайте* адрес биржи (Binance, Bybit)\n"
        "• Выплаты на биржевые адреса могут быть *УТЕРЯНЫ*!\n\n"
        "Формат: `0x...` (42 символа)",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown",
    )
    await state.set_state(WalletChangeStates.awaiting_new_wallet)


@router.message(WalletChangeStates.awaiting_new_wallet, F.text)
async def process_new_wallet(
    message: Message,
    state: FSMContext,
) -> None:
    """Process new wallet address."""
    new_wallet = message.text.strip()

    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=settings_keyboard())
        return

    # BEP-20 validation (basic)
    if not re.match(r"^0x[a-fA-F0-9]{40}$", new_wallet):
        await message.answer(
            "❌ Неверный формат адреса кошелька.\n"
            "Адрес должен начинаться с 0x и содержать 42 символа.\n\n"
            "Попробуйте еще раз или нажмите '❌ Отмена'.",
            reply_markup=cancel_keyboard(),
        )
        return

    await state.update_data(new_wallet=new_wallet)
    await message.answer(
        "🔒 Введите ваш финансовый пароль для подтверждения операции:",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(WalletChangeStates.awaiting_financial_password)


@router.message(WalletChangeStates.awaiting_financial_password, F.text)
async def process_financial_password(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    **data: Any,
) -> None:
    """Process financial password and execute change."""
    password = message.text.strip()

    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=settings_keyboard())
        return

    data_state = await state.get_data()
    new_wallet = data_state.get("new_wallet")

    user_service = UserService(session)
    success, error = await user_service.change_wallet(
        user_id=user.id,
        new_wallet_address=new_wallet,
        financial_password=password,
    )

    if success:
        await state.clear()
        
        # Get blacklist info for main menu
        from app.repositories.blacklist_repository import BlacklistRepository
        blacklist_repo = BlacklistRepository(session)
        blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
        is_admin = data.get("is_admin", False)

        await message.answer(
            f"✅ Ваш кошелек успешно изменен на:\n`{new_wallet}`",
            parse_mode="Markdown",
            reply_markup=main_menu_reply_keyboard(
                user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
            ),
        )
    else:
        if "Invalid financial password" in error:
             await message.answer(
                "❌ Неверный финансовый пароль.\n"
                "Попробуйте еще раз или нажмите '❌ Отмена'.",
                reply_markup=cancel_keyboard(),
            )
        else:
            # Other error (e.g. wallet already used)
            await state.clear()
            await message.answer(
                f"❌ Ошибка при смене кошелька: {error}",
                reply_markup=settings_keyboard(),
            )

