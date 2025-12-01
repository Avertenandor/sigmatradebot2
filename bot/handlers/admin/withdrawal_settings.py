"""
Admin withdrawal settings handler.
"""

from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.global_settings_repository import GlobalSettingsRepository
from bot.states.admin_withdrawal_settings import AdminWithdrawalSettingsStates
from bot.keyboards.reply import cancel_keyboard, admin_withdrawals_keyboard
from bot.utils.admin_utils import clear_state_preserve_admin_token

router = Router()


@router.message(F.text == "⚙️ Настройки выплат")
async def show_withdrawal_settings(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show withdrawal settings menu."""
    # Check admin
    if not data.get("is_admin"):
        return

    await clear_state_preserve_admin_token(state)
    
    repo = GlobalSettingsRepository(session)
    settings = await repo.get_settings()
    
    limit_status = "✅ Включено" if settings.is_daily_limit_enabled else "❌ Выключено"
    auto_status = "✅ Включен" if settings.auto_withdrawal_enabled else "❌ Выключен"
    limit_val = f"{settings.daily_withdrawal_limit} USDT" if settings.daily_withdrawal_limit else "Не задан"
    service_fee = getattr(settings, "withdrawal_service_fee", Decimal("0.00"))
    
    text = (
        f"⚙️ *Настройки выплат*\n\n"
        f"💵 Мин. вывод: `{settings.min_withdrawal_amount} USDT`\n"
        f"🛡 Дневной лимит: `{limit_val}`\n"
        f"🔒 Ограничение лимита: {limit_status}\n"
        f"⚡️ Авто-вывод: {auto_status}\n"
        f"💸 Комиссия сервиса: `{service_fee}%`\n\n"
        f"_Авто-вывод работает по правилу x5 (Депозиты * 5 >= Выводы + Запрос)._"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Изм. Мин. Вывод", callback_data="admin_ws_min")],
        [InlineKeyboardButton(text="🛡 Изм. Дневной Лимит", callback_data="admin_ws_limit_val")],
        [InlineKeyboardButton(text="💸 Изм. Комиссию (%)", callback_data="admin_ws_fee")],
        [InlineKeyboardButton(
            text=f"{'🔴 Выключить' if settings.is_daily_limit_enabled else '🟢 Включить'} Лимит", 
            callback_data="admin_ws_toggle_limit"
        )],
        [InlineKeyboardButton(
            text=f"{'🔴 Выключить' if settings.auto_withdrawal_enabled else '🟢 Включить'} Авто-вывод", 
            callback_data="admin_ws_toggle_auto"
        )],
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data == "admin_ws_toggle_limit")
async def toggle_limit(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Toggle daily limit."""
    repo = GlobalSettingsRepository(session)
    settings = await repo.get_settings()
    await repo.update_settings(is_daily_limit_enabled=not settings.is_daily_limit_enabled)
    
    await callback.answer("Настройка обновлена")
    await _refresh_menu(callback.message, session)


@router.callback_query(F.data == "admin_ws_toggle_auto")
async def toggle_auto(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Toggle auto withdrawal."""
    repo = GlobalSettingsRepository(session)
    settings = await repo.get_settings()
    await repo.update_settings(auto_withdrawal_enabled=not settings.auto_withdrawal_enabled)
    
    await callback.answer("Настройка обновлена")
    await _refresh_menu(callback.message, session)


async def _refresh_menu(message: Message, session: AsyncSession):
    repo = GlobalSettingsRepository(session)
    settings = await repo.get_settings()
    
    limit_status = "✅ Включено" if settings.is_daily_limit_enabled else "❌ Выключено"
    auto_status = "✅ Включен" if settings.auto_withdrawal_enabled else "❌ Выключен"
    limit_val = f"{settings.daily_withdrawal_limit} USDT" if settings.daily_withdrawal_limit else "Не задан"
    service_fee = getattr(settings, "withdrawal_service_fee", Decimal("0.00"))
    
    text = (
        f"⚙️ *Настройки выплат*\n\n"
        f"💵 Мин. вывод: `{settings.min_withdrawal_amount} USDT`\n"
        f"🛡 Дневной лимит: `{limit_val}`\n"
        f"🔒 Ограничение лимита: {limit_status}\n"
        f"⚡️ Авто-вывод: {auto_status}\n"
        f"💸 Комиссия сервиса: `{service_fee}%`\n\n"
        f"_Авто-вывод работает по правилу x5 (Депозиты * 5 >= Выводы + Запрос)._"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Изм. Мин. Вывод", callback_data="admin_ws_min")],
        [InlineKeyboardButton(text="🛡 Изм. Дневной Лимит", callback_data="admin_ws_limit_val")],
        [InlineKeyboardButton(text="💸 Изм. Комиссию (%)", callback_data="admin_ws_fee")],
        [InlineKeyboardButton(
            text=f"{'🔴 Выключить' if settings.is_daily_limit_enabled else '🟢 Включить'} Лимит", 
            callback_data="admin_ws_toggle_limit"
        )],
        [InlineKeyboardButton(
            text=f"{'🔴 Выключить' if settings.auto_withdrawal_enabled else '🟢 Включить'} Авто-вывод", 
            callback_data="admin_ws_toggle_auto"
        )],
    ])
    
    try:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception:
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data == "admin_ws_min")
async def ask_min_amount(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Ask for min amount."""
    await state.set_state(AdminWithdrawalSettingsStates.waiting_for_min_amount)
    await callback.message.answer(
        "Введите новую минимальную сумму вывода (например: 5.0):",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_ws_limit_val")
async def ask_daily_limit(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Ask for daily limit."""
    await state.set_state(AdminWithdrawalSettingsStates.waiting_for_daily_limit)
    await callback.message.answer(
        "Введите новый дневной лимит (например: 5000):",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_ws_fee")
async def ask_service_fee(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Ask for service fee."""
    await state.set_state(AdminWithdrawalSettingsStates.waiting_for_service_fee)
    await callback.message.answer(
        "Введите новую комиссию сервиса в % (например: 5.0):",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(AdminWithdrawalSettingsStates.waiting_for_service_fee)
async def set_service_fee(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await message.answer("Отменено", reply_markup=admin_withdrawals_keyboard())
        return

    try:
        val = Decimal(message.text.strip())
        if val < 0 or val > 100:
            raise ValueError
    except:
        await message.answer("❌ Введите корректное число от 0 до 100")
        return

    repo = GlobalSettingsRepository(session)
    await repo.update_settings(withdrawal_service_fee=val)
    
    await message.answer(f"✅ Комиссия сервиса установлена: {val}%", reply_markup=admin_withdrawals_keyboard())
    await clear_state_preserve_admin_token(state)
    
    settings = await repo.get_settings()
    await _refresh_menu_new_msg(message, settings)


@router.message(AdminWithdrawalSettingsStates.waiting_for_min_amount)
async def set_min_amount(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await message.answer("Отменено", reply_markup=admin_withdrawals_keyboard())
        return

    try:
        val = Decimal(message.text.strip())
        if val <= 0:
            raise ValueError
    except:
        await message.answer("❌ Введите корректное положительное число")
        return

    repo = GlobalSettingsRepository(session)
    await repo.update_settings(min_withdrawal_amount=val)
    
    await message.answer(f"✅ Минимальный вывод установлен: {val} USDT", reply_markup=admin_withdrawals_keyboard())
    await clear_state_preserve_admin_token(state)
    
    settings = await repo.get_settings()
    await _refresh_menu_new_msg(message, settings)


@router.message(AdminWithdrawalSettingsStates.waiting_for_daily_limit)
async def set_daily_limit(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await message.answer("Отменено", reply_markup=admin_withdrawals_keyboard())
        return

    try:
        val = Decimal(message.text.strip())
        if val <= 0:
            raise ValueError
    except:
        await message.answer("❌ Введите корректное положительное число")
        return

    repo = GlobalSettingsRepository(session)
    await repo.update_settings(daily_withdrawal_limit=val)
    
    await message.answer(f"✅ Дневной лимит установлен: {val} USDT", reply_markup=admin_withdrawals_keyboard())
    await clear_state_preserve_admin_token(state)
    
    settings = await repo.get_settings()
    await _refresh_menu_new_msg(message, settings)


async def _refresh_menu_new_msg(message: Message, settings):
    limit_status = "✅ Включено" if settings.is_daily_limit_enabled else "❌ Выключено"
    auto_status = "✅ Включен" if settings.auto_withdrawal_enabled else "❌ Выключен"
    limit_val = f"{settings.daily_withdrawal_limit} USDT" if settings.daily_withdrawal_limit else "Не задан"
    service_fee = getattr(settings, "withdrawal_service_fee", Decimal("0.00"))
    
    text = (
        f"⚙️ *Настройки выплат*\n\n"
        f"💵 Мин. вывод: `{settings.min_withdrawal_amount} USDT`\n"
        f"🛡 Дневной лимит: `{limit_val}`\n"
        f"🔒 Ограничение лимита: {limit_status}\n"
        f"⚡️ Авто-вывод: {auto_status}\n"
        f"💸 Комиссия сервиса: `{service_fee}%`\n\n"
        f"_Авто-вывод работает по правилу x5 (Депозиты * 5 >= Выводы + Запрос)._"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Изм. Мин. Вывод", callback_data="admin_ws_min")],
        [InlineKeyboardButton(text="🛡 Изм. Дневной Лимит", callback_data="admin_ws_limit_val")],
        [InlineKeyboardButton(text="💸 Изм. Комиссию (%)", callback_data="admin_ws_fee")],
        [InlineKeyboardButton(
            text=f"{'🔴 Выключить' if settings.is_daily_limit_enabled else '🟢 Включить'} Лимит", 
            callback_data="admin_ws_toggle_limit"
        )],
        [InlineKeyboardButton(
            text=f"{'🔴 Выключить' if settings.auto_withdrawal_enabled else '🟢 Включить'} Авто-вывод", 
            callback_data="admin_ws_toggle_auto"
        )],
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

