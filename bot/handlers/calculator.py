"""
Calculator handler.

Provides ROI calculator for users to estimate earnings.
Uses dynamic rates from DepositVersion in database.
"""

from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from bot.keyboards.reply import main_menu_reply_keyboard, cancel_keyboard
from bot.utils.menu_buttons import is_menu_button

router = Router(name="calculator")


class CalculatorStates(StatesGroup):
    """Calculator flow states."""

    waiting_for_amount = State()


async def get_deposit_versions(session: AsyncSession) -> dict:
    """Get deposit versions from database."""
    from app.repositories.deposit_level_version_repository import DepositLevelVersionRepository
    
    repo = DepositLevelVersionRepository(session)
    versions = await repo.get_all_active_levels()
    
    result = {}
    for v in versions:
        result[v.level_number] = {
            "amount": v.amount,  # Decimal
            "roi_percent": v.roi_percent,  # Decimal
            "roi_cap": v.roi_cap_percent,  # Decimal or None
        }
    return result


@router.message(F.text == "📊 Калькулятор")
async def show_calculator(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show calculator menu with dynamic levels from DB."""
    await state.clear()

    # Get levels from database
    levels = await get_deposit_versions(session)
    
    if not levels:
        await message.answer(
            "❌ Уровни депозитов не настроены. Обратитесь в поддержку."
        )
        return

    levels_text = ""
    for lvl in sorted(levels.keys()):
        info = levels[lvl]
        cap_info = f" (ROI cap {int(info['roi_cap'])}%)" if info["roi_cap"] else ""
        levels_text += f"• Level {lvl}: {int(info['amount'])} USDT{cap_info}\n"

    text = (
        "📊 *Калькулятор доходности*\n\n"
        "Введите сумму депозита (USDT) для расчёта:\n\n"
        f"💡 *Доступные уровни:*\n{levels_text}\n"
        "Введите сумму или нажмите '❌ Отмена' для выхода:"
    )

    await message.answer(text, parse_mode="Markdown", reply_markup=cancel_keyboard())
    await state.set_state(CalculatorStates.waiting_for_amount)


@router.message(CalculatorStates.waiting_for_amount)
async def process_calculator_amount(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Process calculator amount input with dynamic rates from DB."""
    # Check for menu button or cancel
    if is_menu_button(message.text or "") or message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_menu_reply_keyboard())
        return

    # Parse amount
    try:
        amount = Decimal(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except (ValueError, TypeError):
        await message.answer(
            "❌ Введите корректную сумму (число).\n"
            "Например: 100 или 150.50"
        )
        return

    # Get levels from database
    levels = await get_deposit_versions(session)
    if not levels:
        await message.answer("❌ Уровни депозитов не настроены.")
        await state.clear()
        return

    # Find matching level
    level = None
    for lvl, info in levels.items():
        if amount == info["amount"]:
            level = lvl
            break

    if not level:
        # Find closest level
        closest_level = min(
            levels.keys(),
            key=lambda x: abs(levels[x]["amount"] - amount),
        )
        await message.answer(
            f"⚠️ Сумма {amount} USDT не соответствует ни одному уровню.\n\n"
            f"Ближайший уровень: Level {closest_level} "
            f"({int(levels[closest_level]['amount'])} USDT)\n\n"
            "Введите точную сумму уровня депозита."
        )
        return

    # Calculate projections (using Decimal)
    level_info = levels[level]
    roi_percent = level_info["roi_percent"]
    daily_roi = amount * roi_percent / Decimal("100")
    weekly_roi = daily_roi * 7
    monthly_roi = daily_roi * 30
    
    # ROI cap calculations
    if level_info["roi_cap"]:
        max_roi = amount * level_info["roi_cap"] / Decimal("100")
        days_to_cap = int(max_roi / daily_roi) if daily_roi > 0 else 0
        cap_text = (
            f"\n🎯 *ROI Cap:* {int(level_info['roi_cap'])}%\n"
            f"💰 Максимум: *{max_roi:.2f} USDT*\n"
            f"📅 Достижение: ~{days_to_cap} дней"
        )
    else:
        cap_text = "\n♾️ *Без ограничения ROI*"

    text = (
        f"📊 *Калькулятор: Level {level}*\n\n"
        f"💵 Депозит: *{amount} USDT*\n"
        f"📈 ROI: *{roi_percent:.3f}%* в день\n\n"
        f"*Прогноз заработка:*\n"
        f"• За день: *{daily_roi:.2f} USDT*\n"
        f"• За неделю: *{weekly_roi:.2f} USDT*\n"
        f"• За месяц: *{monthly_roi:.2f} USDT*"
        f"{cap_text}\n\n"
        f"⚠️ _Расчёт приблизительный. Фактический ROI может отличаться._"
    )

    await message.answer(text, parse_mode="Markdown")
    await state.clear()

