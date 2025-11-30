"""
Calculator handler.

Provides ROI calculator for users to estimate earnings.
"""

from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.models.user import User
from bot.keyboards.reply import main_menu_reply_keyboard
from bot.utils.menu_buttons import is_menu_button

router = Router(name="calculator")


class CalculatorStates(StatesGroup):
    """Calculator flow states."""

    waiting_for_amount = State()


# Deposit levels and amounts
DEPOSIT_LEVELS = {
    1: {"amount": 50, "roi_percent": 1.117, "roi_cap": 500},
    2: {"amount": 100, "roi_percent": 1.117, "roi_cap": None},
    3: {"amount": 150, "roi_percent": 1.117, "roi_cap": None},
    4: {"amount": 200, "roi_percent": 1.117, "roi_cap": None},
    5: {"amount": 300, "roi_percent": 1.117, "roi_cap": None},
}


@router.message(F.text == "📊 Калькулятор")
async def show_calculator(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show calculator menu."""
    await state.clear()

    text = (
        "📊 *Калькулятор доходности*\n\n"
        "Введите сумму депозита (USDT) для расчёта:\n\n"
        "💡 *Доступные уровни:*\n"
        "• Level 1: 50 USDT (ROI cap 500%)\n"
        "• Level 2: 100 USDT\n"
        "• Level 3: 150 USDT\n"
        "• Level 4: 200 USDT\n"
        "• Level 5: 300 USDT\n\n"
        "Введите сумму или нажмите '📊 Главное меню' для выхода:"
    )

    await message.answer(text, parse_mode="Markdown")
    await state.set_state(CalculatorStates.waiting_for_amount)


@router.message(CalculatorStates.waiting_for_amount)
async def process_calculator_amount(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Process calculator amount input."""
    user: User | None = data.get("user")

    # Check for menu button
    if is_menu_button(message.text or ""):
        await state.clear()
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

    # Find matching level
    level = None
    for lvl, info in DEPOSIT_LEVELS.items():
        if amount == Decimal(str(info["amount"])):
            level = lvl
            break

    if not level:
        # Find closest level
        closest_level = min(
            DEPOSIT_LEVELS.keys(),
            key=lambda x: abs(DEPOSIT_LEVELS[x]["amount"] - float(amount)),
        )
        await message.answer(
            f"⚠️ Сумма {amount} USDT не соответствует ни одному уровню.\n\n"
            f"Ближайший уровень: Level {closest_level} "
            f"({DEPOSIT_LEVELS[closest_level]['amount']} USDT)\n\n"
            "Введите точную сумму уровня депозита."
        )
        return

    # Calculate projections
    level_info = DEPOSIT_LEVELS[level]
    daily_roi = float(amount) * level_info["roi_percent"] / 100
    weekly_roi = daily_roi * 7
    monthly_roi = daily_roi * 30
    
    # ROI cap calculations
    if level_info["roi_cap"]:
        max_roi = float(amount) * level_info["roi_cap"] / 100
        days_to_cap = int(max_roi / daily_roi) if daily_roi > 0 else 0
        cap_text = (
            f"\n🎯 *ROI Cap:* {level_info['roi_cap']}%\n"
            f"💰 Максимум: *{max_roi:.2f} USDT*\n"
            f"📅 Достижение: ~{days_to_cap} дней"
        )
    else:
        cap_text = "\n♾️ *Без ограничения ROI*"

    text = (
        f"📊 *Калькулятор: Level {level}*\n\n"
        f"💵 Депозит: *{amount} USDT*\n"
        f"📈 ROI: *{level_info['roi_percent']}%* в день\n\n"
        f"*Прогноз заработка:*\n"
        f"• За день: *{daily_roi:.2f} USDT*\n"
        f"• За неделю: *{weekly_roi:.2f} USDT*\n"
        f"• За месяц: *{monthly_roi:.2f} USDT*"
        f"{cap_text}\n\n"
        f"⚠️ _Расчёт приблизительный. Фактический ROI может отличаться._"
    )

    await message.answer(text, parse_mode="Markdown")
    await state.clear()

