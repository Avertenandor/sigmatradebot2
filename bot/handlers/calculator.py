"""
Calculator handler.

Provides comprehensive ROI calculator for users to estimate earnings.
Uses dynamic rates from DepositVersion in database.
Shows all levels with their current settings and availability.
"""

from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from bot.keyboards.reply import main_menu_reply_keyboard
from bot.utils.menu_buttons import is_menu_button

router = Router(name="calculator")


class CalculatorStates(StatesGroup):
    """Calculator flow states."""

    selecting_level = State()
    viewing_details = State()


async def get_all_deposit_levels(session: AsyncSession) -> dict:
    """
    Get ALL deposit levels from database (active and inactive).
    
    Returns dict with level info including is_active status.
    All Decimal values converted to str for JSON serialization (FSM Redis).
    """
    from app.repositories.deposit_level_version_repository import (
        DepositLevelVersionRepository,
    )
    
    repo = DepositLevelVersionRepository(session)
    
    result = {}
    for level_num in range(1, 6):
        version = await repo.get_current_version(level_num)
        if version:
            # Convert Decimal to str for JSON serialization in FSM
            result[level_num] = {
                "amount": str(version.amount),
                "roi_percent": str(version.roi_percent),
                "roi_cap": version.roi_cap_percent,  # int, OK
                "is_active": version.is_active,
            }
    
    return result


def calculator_keyboard(levels: dict) -> any:
    """Create calculator keyboard with level buttons."""
    from decimal import Decimal as Dec
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    from aiogram.utils.keyboard import ReplyKeyboardBuilder
    
    builder = ReplyKeyboardBuilder()
    
    for level_num in sorted(levels.keys()):
        info = levels[level_num]
        amount = int(Dec(info["amount"]))
        
        if info["is_active"]:
            button_text = f"📊 Level {level_num} ({amount} USDT)"
        else:
            button_text = f"🔒 Level {level_num} ({amount} USDT) - Закрыт"
        
        builder.row(KeyboardButton(text=button_text))
    
    # Navigation
    builder.row(
        KeyboardButton(text="📋 Сравнить все уровни"),
    )
    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )
    
    return builder.as_markup(resize_keyboard=True)


def format_decimal(value: Decimal, decimals: int = 2) -> str:
    """Format decimal to string with specified decimals."""
    return f"{value:.{decimals}f}"


@router.message(F.text == "📊 Калькулятор")
async def show_calculator(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show calculator menu with all levels."""
    await state.clear()
    
    levels = await get_all_deposit_levels(session)
    
    if not levels:
        await message.answer(
            "❌ Уровни депозитов не настроены. Обратитесь в поддержку."
        )
        return
    
    # Build levels overview
    levels_text = ""
    for lvl in sorted(levels.keys()):
        info = levels[lvl]
        status = "✅" if info["is_active"] else "🔒"
        roi = Decimal(info["roi_percent"])
        cap = info["roi_cap"]
        amount = Decimal(info["amount"])
        
        levels_text += (
            f"{status} *Level {lvl}:* {int(amount)} USDT\n"
            f"   📈 ROI: {format_decimal(roi, 3)}%/день"
        )
        if cap:
            levels_text += f" | Cap: {cap}%"
        levels_text += "\n"
    
    text = (
        "📊 *Калькулятор доходности*\n\n"
        f"*Текущие условия:*\n{levels_text}\n"
        "Выберите уровень для детального расчёта\n"
        "или нажмите *'📋 Сравнить все уровни'*"
    )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=calculator_keyboard(levels),
    )
    await state.set_state(CalculatorStates.selecting_level)
    await state.update_data(levels=levels)


@router.message(CalculatorStates.selecting_level, F.text == "📋 Сравнить все уровни")
async def show_comparison(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show detailed comparison of all levels."""
    state_data = await state.get_data()
    levels = state_data.get("levels") or await get_all_deposit_levels(session)
    
    if not levels:
        await message.answer("❌ Уровни не найдены.")
        return
    
    text = "📋 *Сравнение всех уровней*\n\n"
    
    for lvl in sorted(levels.keys()):
        info = levels[lvl]
        amount = Decimal(info["amount"])
        roi = Decimal(info["roi_percent"])
        cap = info["roi_cap"]
        is_active = info["is_active"]
        
        status = "✅ Доступен" if is_active else "🔒 Закрыт"
        
        # Calculate projections
        daily = amount * roi / Decimal("100")
        weekly = daily * 7
        monthly = daily * 30
        yearly = daily * 365
        
        text += f"{'═' * 25}\n"
        text += f"*Level {lvl}* — {status}\n"
        text += f"💵 Депозит: *{int(amount)} USDT*\n"
        text += f"📈 ROI: *{format_decimal(roi, 3)}%* в день\n\n"
        
        text += f"*Прогноз заработка:*\n"
        text += f"• День: *{format_decimal(daily)} USDT*\n"
        text += f"• Неделя: *{format_decimal(weekly)} USDT*\n"
        text += f"• Месяц: *{format_decimal(monthly)} USDT*\n"
        text += f"• Год: *{format_decimal(yearly)} USDT*\n"
        
        if cap:
            max_roi = amount * Decimal(cap) / Decimal("100")
            days_to_cap = int(max_roi / daily) if daily > 0 else 0
            text += (
                f"\n🎯 *ROI Cap:* {cap}% = *{format_decimal(max_roi)} USDT*\n"
                f"📅 Достижение: ~*{days_to_cap} дней*\n"
            )
        else:
            text += "\n♾️ *Без ограничения ROI*\n"
        
        text += "\n"
    
    text += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ _Расчёт приблизительный.\n"
        "Фактический ROI зависит от настроек системы._"
    )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=calculator_keyboard(levels),
    )


@router.message(CalculatorStates.selecting_level, F.text.startswith("📊 Level"))
async def show_level_details(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show detailed calculation for specific level."""
    import re
    
    # Extract level number
    match = re.search(r"Level (\d+)", message.text)
    if not match:
        await message.answer("❌ Не удалось определить уровень.")
        return
    
    level_num = int(match.group(1))
    
    state_data = await state.get_data()
    levels = state_data.get("levels") or await get_all_deposit_levels(session)
    
    if level_num not in levels:
        await message.answer(f"❌ Level {level_num} не найден.")
        return
    
    info = levels[level_num]
    amount = Decimal(info["amount"])
    roi = Decimal(info["roi_percent"])
    cap = info["roi_cap"]
    is_active = info["is_active"]
    
    status = "✅ Доступен для покупки" if is_active else "🔒 Временно закрыт"
    
    # Calculate projections
    daily = amount * roi / Decimal("100")
    weekly = daily * 7
    monthly = daily * 30
    quarterly = daily * 90
    yearly = daily * 365
    
    text = (
        f"📊 *Калькулятор: Level {level_num}*\n\n"
        f"*Статус:* {status}\n"
        f"{'═' * 25}\n\n"
        f"💵 *Депозит:* {int(amount)} USDT\n"
        f"📈 *ROI:* {format_decimal(roi, 3)}% в день\n\n"
        f"*💰 Прогноз заработка:*\n"
        f"┌─────────────────────────\n"
        f"│ 📅 *1 день:*     {format_decimal(daily)} USDT\n"
        f"│ 📅 *7 дней:*     {format_decimal(weekly)} USDT\n"
        f"│ 📅 *30 дней:*    {format_decimal(monthly)} USDT\n"
        f"│ 📅 *90 дней:*    {format_decimal(quarterly)} USDT\n"
        f"│ 📅 *365 дней:*   {format_decimal(yearly)} USDT\n"
        f"└─────────────────────────\n\n"
    )
    
    if cap:
        max_roi = amount * Decimal(cap) / Decimal("100")
        days_to_cap = int(max_roi / daily) if daily > 0 else 0
        months_to_cap = round(days_to_cap / 30, 1)
        
        text += (
            f"🎯 *ROI Cap: {cap}%*\n"
            f"├─ Максимум: *{format_decimal(max_roi)} USDT*\n"
            f"├─ Достижение: ~*{days_to_cap} дней* (~{months_to_cap} мес.)\n"
            f"└─ Доходность: *{cap}%* от депозита\n\n"
        )
        
        # ROI breakdown
        roi_50 = max_roi * Decimal("0.5")
        days_50 = int(roi_50 / daily) if daily > 0 else 0
        roi_100 = max_roi
        days_100 = days_to_cap
        
        text += (
            f"*📊 Этапы достижения:*\n"
            f"• 50% ({format_decimal(roi_50)} USDT): ~{days_50} дней\n"
            f"• 100% ({format_decimal(roi_100)} USDT): ~{days_100} дней\n"
        )
    else:
        text += "♾️ *Без ограничения ROI* — неограниченный заработок\n"
    
    text += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ _Расчёт приблизительный.\n"
        "Фактический ROI может отличаться от прогноза._"
    )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=calculator_keyboard(levels),
    )


@router.message(CalculatorStates.selecting_level, F.text.startswith("🔒 Level"))
async def show_locked_level(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show info about locked level."""
    import re
    
    match = re.search(r"Level (\d+)", message.text)
    if not match:
        return
    
    level_num = int(match.group(1))
    
    state_data = await state.get_data()
    levels = state_data.get("levels") or await get_all_deposit_levels(session)
    
    if level_num not in levels:
        return
    
    info = levels[level_num]
    amount = Decimal(info["amount"])
    roi = Decimal(info["roi_percent"])
    cap = info["roi_cap"]
    
    # Calculate projections anyway
    daily = amount * roi / Decimal("100")
    weekly = daily * 7
    monthly = daily * 30
    
    text = (
        f"🔒 *Level {level_num} — Временно закрыт*\n\n"
        f"Этот уровень пока недоступен для покупки.\n"
        f"Следите за обновлениями!\n\n"
        f"*Условия уровня (когда откроется):*\n"
        f"💵 Депозит: {int(amount)} USDT\n"
        f"📈 ROI: {format_decimal(roi, 3)}% в день\n\n"
        f"*Потенциальный заработок:*\n"
        f"• День: {format_decimal(daily)} USDT\n"
        f"• Неделя: {format_decimal(weekly)} USDT\n"
        f"• Месяц: {format_decimal(monthly)} USDT\n"
    )
    
    if cap:
        max_roi = amount * Decimal(cap) / Decimal("100")
        text += f"\n🎯 ROI Cap: {cap}% ({format_decimal(max_roi)} USDT)\n"
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=calculator_keyboard(levels),
    )


@router.message(CalculatorStates.selecting_level)
async def handle_calculator_other(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle other inputs in calculator state."""
    # Check for menu buttons
    if is_menu_button(message.text or ""):
        await state.clear()
        user = data.get("user")
        is_admin = data.get("is_admin", False)
        blacklist_entry = data.get("blacklist_entry")
        await message.answer(
            "📊 Главное меню",
            reply_markup=main_menu_reply_keyboard(
                user=user,
                blacklist_entry=blacklist_entry,
                is_admin=is_admin,
            ),
        )
        return
    
    # Unknown input
    await message.answer(
        "❓ Выберите уровень из меню или нажмите '📊 Главное меню' для выхода."
    )
