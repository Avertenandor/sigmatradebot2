"""
Calculator handler.

Provides comprehensive ROI calculator for users to estimate earnings.
Uses dynamic rates from DepositVersion and ROI corridor settings.
Shows realistic projections with referral program benefits.
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
    custom_amount = State()


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


async def get_roi_corridor(session: AsyncSession) -> dict:
    """Get ROI corridor settings from global_settings."""
    from sqlalchemy import select
    from app.models.global_settings import GlobalSettings

    stmt = select(GlobalSettings).where(GlobalSettings.id == 1)
    result = await session.execute(stmt)
    settings = result.scalar_one_or_none()

    if settings and settings.roi_settings:
        roi = settings.roi_settings
        return {
            "min": Decimal(roi.get("LEVEL_1_ROI_MIN", "1.0")),
            "max": Decimal(roi.get("LEVEL_1_ROI_MAX", "3.0")),
            "mode": roi.get("LEVEL_1_ROI_MODE", "custom"),
            "period_hours": int(roi.get("REWARD_ACCRUAL_PERIOD_HOURS", "6")),
        }

    # Defaults
    return {
        "min": Decimal("1.0"),
        "max": Decimal("3.0"),
        "mode": "custom",
        "period_hours": 6,
    }


async def get_all_deposit_levels(session: AsyncSession) -> dict:
    """Get ALL deposit levels from database."""
    from app.repositories.deposit_level_version_repository import (
        DepositLevelVersionRepository,
    )

    repo = DepositLevelVersionRepository(session)

    result = {}
    for level_num in range(1, 6):
        version = await repo.get_current_version(level_num)
        if version:
            result[level_num] = {
                "amount": str(version.amount),
                "roi_percent": str(version.roi_percent),
                "roi_cap": version.roi_cap_percent,
                "is_active": version.is_active,
            }

    return result


def calculator_keyboard(levels: dict) -> any:
    """Create calculator keyboard with level buttons."""
    from aiogram.types import KeyboardButton
    from aiogram.utils.keyboard import ReplyKeyboardBuilder

    builder = ReplyKeyboardBuilder()

    for level_num in sorted(levels.keys()):
        info = levels[level_num]
        amount = int(Decimal(info["amount"]))

        if info["is_active"]:
            button_text = f"💎 Level {level_num} • {amount} USDT"
        else:
            button_text = f"🔒 Level {level_num} • {amount} USDT"

        builder.row(KeyboardButton(text=button_text))

    # Navigation
    builder.row(
        KeyboardButton(text="📊 Сравнить уровни"),
        KeyboardButton(text="🧮 Свой расчёт"),
    )
    builder.row(
        KeyboardButton(text="🏠 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def format_money(value: Decimal) -> str:
    """Format money: 1234.56 -> 1 234.56"""
    int_part = int(value)
    dec_part = value - int_part

    formatted_int = f"{int_part:,}".replace(",", " ")

    if dec_part > 0:
        dec_str = f"{dec_part:.2f}"[1:]
        return f"{formatted_int}{dec_str}"
    return formatted_int


def format_percent(value: Decimal) -> str:
    """Format percentage: 1.500 -> 1.5, 2.000 -> 2"""
    formatted = f"{value:.2f}".rstrip("0").rstrip(".")
    return formatted


def progress_bar(current: Decimal, total: Decimal, length: int = 10) -> str:
    """Create visual progress bar."""
    if total == 0:
        return "░" * length

    percent = min(float(current / total), 1.0)
    filled = int(percent * length)
    return "█" * filled + "░" * (length - filled)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN CALCULATOR ENTRY
# ═══════════════════════════════════════════════════════════════════════════


@router.message(F.text == "📊 Калькулятор")
async def show_calculator(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show calculator welcome screen."""
    await state.clear()

    levels = await get_all_deposit_levels(session)
    corridor = await get_roi_corridor(session)

    if not levels:
        await message.answer(
            "❌ Уровни депозитов не настроены. Обратитесь в поддержку."
        )
        return

    # Calculate daily ROI (accruals per day × ROI per accrual)
    period = corridor["period_hours"]
    accruals_per_day = Decimal(24) / Decimal(period)
    daily_min = corridor["min"] * accruals_per_day
    daily_max = corridor["max"] * accruals_per_day
    daily_avg = (daily_min + daily_max) / 2

    # Build levels preview
    levels_preview = ""
    for lvl in sorted(levels.keys()):
        info = levels[lvl]
        status = "✅" if info["is_active"] else "🔒"
        amount = int(Decimal(info["amount"]))
        levels_preview += f"{status} Level {lvl}: "
        levels_preview += f"*{format_money(Decimal(amount))} USDT*\n"

    text = f"""
💰 *КАЛЬКУЛЯТОР ДОХОДНОСТИ*
━━━━━━━━━━━━━━━━━━━━━━━

📈 *Текущие условия:*
• Начисления: каждые *{period}ч* ({int(accruals_per_day)}× в день)
• За начисление: *{format_percent(corridor['min'])}—{format_percent(corridor['max'])}%*
• В день: *{format_percent(daily_min)}—{format_percent(daily_max)}%* (~{format_percent(daily_avg)}%)

{levels_preview}
💎 *Реферальная программа:*
├ 1 линия: *3%* от депозитов и дохода
├ 2 линия: *2%* от депозитов и дохода
└ 3 линия: *5%* от депозитов и дохода

👇 *Выберите уровень для расчёта:*
    """.strip()

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=calculator_keyboard(levels),
    )
    await state.set_state(CalculatorStates.selecting_level)
    await state.update_data(
        levels=levels,
        corridor={
            "min": str(corridor["min"]),
            "max": str(corridor["max"]),
            "period_hours": corridor["period_hours"],
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# LEVEL COMPARISON
# ═══════════════════════════════════════════════════════════════════════════


@router.message(
    CalculatorStates.selecting_level, F.text == "📊 Сравнить уровни"
)
async def show_comparison(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show side-by-side level comparison."""
    state_data = await state.get_data()
    levels = state_data.get("levels") or await get_all_deposit_levels(session)
    corridor_data = state_data.get("corridor") or {}

    if not levels:
        await message.answer("❌ Уровни не найдены.")
        return

    # Get ROI from corridor (per accrual, not per day!)
    min_roi = Decimal(corridor_data.get("min", "1.0"))
    max_roi = Decimal(corridor_data.get("max", "3.0"))
    period = int(corridor_data.get("period_hours", 6))
    
    # Calculate DAILY ROI
    accruals_per_day = Decimal(24) / Decimal(period)
    daily_roi_avg = (min_roi + max_roi) / 2 * accruals_per_day

    text = "📊 *СРАВНЕНИЕ УРОВНЕЙ*\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for lvl in sorted(levels.keys()):
        info = levels[lvl]
        amount = Decimal(info["amount"])
        cap = info["roi_cap"]
        is_active = info["is_active"]

        status = "✅ ОТКРЫТ" if is_active else "🔒 СКОРО"

        # Calculate with daily ROI
        daily = amount * daily_roi_avg / Decimal("100")
        monthly = daily * 30

        # Referral bonus
        ref_bonus = amount * Decimal("0.03")

        text += f"*{'═' * 26}*\n"
        text += f"*Level {lvl}* — {status}\n"
        text += f"💵 Депозит: *{format_money(amount)} USDT*\n\n"

        text += f"📈 *Доход (~{format_percent(daily_roi_avg)}%/день):*\n"
        text += f"├ День: *+{format_money(daily)} USDT*\n"
        text += f"└ Месяц: *+{format_money(monthly)} USDT*\n"

        if cap:
            max_roi_amount = amount * Decimal(cap) / Decimal("100")
            days = int(max_roi_amount / daily) if daily > 0 else 0
            text += f"\n🎯 Cap {cap}%: *{format_money(max_roi_amount)}* "
            text += f"за ~{days} дн.\n"

        text += f"\n👥 Реф. бонус: *+{format_money(ref_bonus)}* "
        text += "+ 3% от дохода\n\n"

    text += "━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "_Выберите уровень для деталей_"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=calculator_keyboard(levels),
    )


# ═══════════════════════════════════════════════════════════════════════════
# DETAILED LEVEL VIEW
# ═══════════════════════════════════════════════════════════════════════════


@router.message(CalculatorStates.selecting_level, F.text.startswith("💎 Level"))
async def show_level_details(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show detailed calculation for specific active level."""
    import re

    match = re.search(r"Level (\d+)", message.text)
    if not match:
        await message.answer("❌ Не удалось определить уровень.")
        return

    level_num = int(match.group(1))

    state_data = await state.get_data()
    levels = state_data.get("levels") or await get_all_deposit_levels(session)
    corridor_data = state_data.get("corridor") or {}

    if level_num not in levels:
        await message.answer(f"❌ Level {level_num} не найден.")
        return

    info = levels[level_num]
    amount = Decimal(info["amount"])
    cap = info["roi_cap"]

    # Get ROI corridor (per accrual!)
    min_roi_acc = Decimal(corridor_data.get("min", "1.0"))
    max_roi_acc = Decimal(corridor_data.get("max", "3.0"))
    avg_roi_acc = (min_roi_acc + max_roi_acc) / 2
    period = int(corridor_data.get("period_hours", 6))
    
    # Calculate DAILY ROI
    accruals_per_day = Decimal(24) / Decimal(period)
    daily_roi_min = min_roi_acc * accruals_per_day
    daily_roi_max = max_roi_acc * accruals_per_day
    daily_roi_avg = avg_roi_acc * accruals_per_day

    # Calculate daily income projections
    daily_min = amount * daily_roi_min / Decimal("100")
    daily_avg = amount * daily_roi_avg / Decimal("100")
    daily_max = amount * daily_roi_max / Decimal("100")

    weekly_avg = daily_avg * 7
    monthly_avg = daily_avg * 30
    quarterly_avg = daily_avg * 90

    # Referral calculations (3 partners)
    ref_deposit_l1 = amount * Decimal("0.03") * 3
    ref_deposit_l2 = amount * Decimal("0.02") * 3
    ref_deposit_l3 = amount * Decimal("0.05") * 3
    ref_daily_l1 = daily_avg * Decimal("0.03") * 3
    ref_monthly = ref_daily_l1 * 30

    text = f"""
💎 *LEVEL {level_num}*
{'━' * 28}

💵 *Депозит:* {format_money(amount)} USDT
🎯 *ROI Cap:* {cap}% от депозита
⏰ *Начисления:* каждые {period}ч ({int(accruals_per_day)}× в день)
📊 *За начисление:* {format_percent(min_roi_acc)}—{format_percent(max_roi_acc)}%

{'─' * 28}
📈 *ПРОГНОЗ ДОХОДНОСТИ*
{'─' * 28}

*Ежедневный доход (×{int(accruals_per_day)} начислений):*
├ 📉 Min: *+{format_money(daily_min)}* ({format_percent(daily_roi_min)}%)
├ 📊 Avg: *+{format_money(daily_avg)}* ({format_percent(daily_roi_avg)}%)
└ 📈 Max: *+{format_money(daily_max)}* ({format_percent(daily_roi_max)}%)

*При среднем ROI ~{format_percent(daily_roi_avg)}%/день:*
┌────────────────────────
│ 📅 7 дней:   *+{format_money(weekly_avg)}*
│ 📅 30 дней:  *+{format_money(monthly_avg)}*
│ 📅 90 дней:  *+{format_money(quarterly_avg)}*
└────────────────────────
"""

    if cap:
        max_roi_amount = amount * Decimal(cap) / Decimal("100")
        days_avg = int(max_roi_amount / daily_avg) if daily_avg > 0 else 0
        half_cap = max_roi_amount / 2

        text += f"""
{'─' * 28}
🎯 *ROI CAP {cap}%*
{'─' * 28}

Максимум: *{format_money(max_roi_amount)} USDT*
Достижение: ~*{days_avg} дней*

*Прогресс:*
├ 50%: {progress_bar(Decimal(50), Decimal(100))} {format_money(half_cap)}
└ 100%: {progress_bar(Decimal(100), Decimal(100))} {format_money(max_roi_amount)}
"""

    total_monthly = monthly_avg + ref_deposit_l1 + ref_monthly

    text += f"""
{'─' * 28}
👥 *РЕФЕРАЛЬНАЯ ПРОГРАММА*
{'─' * 28}

*Бонус от депозитов (3 партнёра):*
├ 1 линия (3%): *+{format_money(ref_deposit_l1)}*
├ 2 линия (2%): *+{format_money(ref_deposit_l2)}*
└ 3 линия (5%): *+{format_money(ref_deposit_l3)}*

*От дохода партнёров (3 чел.):*
└ В месяц: *+{format_money(ref_monthly)}*

{'─' * 28}
💰 *ИТОГО ПОТЕНЦИАЛ (3 партнёра):*
├ Свой доход: *{format_money(monthly_avg)}*/мес
├ Рефералы: *+{format_money(ref_deposit_l1 + ref_monthly)}*
└ *ВСЕГО: {format_money(total_monthly)}*/мес
{'━' * 28}

🚀 _Начните инвестировать сейчас!_
    """.strip()

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=calculator_keyboard(levels),
    )


@router.message(
    CalculatorStates.selecting_level, F.text.startswith("🔒 Level")
)
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
    corridor_data = state_data.get("corridor") or {}

    if level_num not in levels:
        return

    info = levels[level_num]
    amount = Decimal(info["amount"])
    cap = info["roi_cap"]

    # Get ROI (per accrual!)
    min_roi_acc = Decimal(corridor_data.get("min", "1.0"))
    max_roi_acc = Decimal(corridor_data.get("max", "3.0"))
    avg_roi_acc = (min_roi_acc + max_roi_acc) / 2
    period = int(corridor_data.get("period_hours", 6))
    
    # Calculate DAILY ROI
    accruals_per_day = Decimal(24) / Decimal(period)
    daily_roi_avg = avg_roi_acc * accruals_per_day

    daily = amount * daily_roi_avg / Decimal("100")
    monthly = daily * 30
    ref_bonus = amount * Decimal("0.03")

    text = f"""
🔒 *LEVEL {level_num} — СКОРО*
{'━' * 28}

⏳ Уровень готовится к запуску!
📢 Следите за анонсами.

{'─' * 28}
*Будущие условия:*
💵 Депозит: *{format_money(amount)} USDT*
🎯 ROI Cap: *{cap}%*

*Потенциальный доход (~{format_percent(daily_roi_avg)}%/день):*
├ День: *+{format_money(daily)}*
└ Месяц: *+{format_money(monthly)}*
{'─' * 28}

💡 *А пока:*
Начните с доступных уровней!

Приведите партнёра на Level {level_num}:
├ Бонус: *+{format_money(ref_bonus)}*
└ + *3%* от его дохода
{'━' * 28}
    """.strip()

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=calculator_keyboard(levels),
    )


# ═══════════════════════════════════════════════════════════════════════════
# CUSTOM AMOUNT CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════


@router.message(CalculatorStates.selecting_level, F.text == "🧮 Свой расчёт")
async def start_custom_calculation(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start custom amount calculation."""
    from aiogram.types import KeyboardButton
    from aiogram.utils.keyboard import ReplyKeyboardBuilder

    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="◀️ Назад к уровням"))

    text = """
🧮 *СВОЙ РАСЧЁТ*
━━━━━━━━━━━━━━━━━━━━━━━

Введите сумму в USDT для расчёта
потенциальной доходности.

📝 *Пример:* `100` или `5000`

_Минимум: 10 USDT_
    """.strip()

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=builder.as_markup(resize_keyboard=True),
    )
    await state.set_state(CalculatorStates.custom_amount)


@router.message(CalculatorStates.custom_amount, F.text == "◀️ Назад к уровням")
async def back_from_custom(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Go back to level selection."""
    await show_calculator(message, state, session, **data)


@router.message(CalculatorStates.custom_amount, F.text == "🧮 Другая сумма")
async def another_custom_amount(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Request another custom amount."""
    await start_custom_calculation(message, state, **data)


@router.message(CalculatorStates.custom_amount)
async def calculate_custom_amount(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Calculate ROI for custom amount."""
    from aiogram.types import KeyboardButton
    from aiogram.utils.keyboard import ReplyKeyboardBuilder

    # Skip if navigation button
    if message.text in ["◀️ Назад к уровням", "🏠 Главное меню"]:
        return

    # Parse amount
    try:
        text_clean = message.text.strip().replace(",", ".").replace(" ", "")
        amount = Decimal(text_clean)
    except Exception:
        await message.answer(
            "❌ Введите корректную сумму.\n\n"
            "Пример: `100` или `5000`",
            parse_mode="Markdown",
        )
        return

    if amount < 10:
        await message.answer("❌ Минимальная сумма: 10 USDT")
        return

    if amount > 1000000:
        await message.answer("❌ Максимальная сумма: 1 000 000 USDT")
        return

    # Get corridor (per accrual!)
    corridor = await get_roi_corridor(session)
    min_roi_acc = corridor["min"]
    max_roi_acc = corridor["max"]
    avg_roi_acc = (min_roi_acc + max_roi_acc) / 2
    period = corridor["period_hours"]
    
    # Calculate DAILY ROI
    accruals_per_day = Decimal(24) / Decimal(period)
    daily_roi_min = min_roi_acc * accruals_per_day
    daily_roi_max = max_roi_acc * accruals_per_day
    daily_roi_avg = avg_roi_acc * accruals_per_day

    # Calculations
    daily_min = amount * daily_roi_min / Decimal("100")
    daily_avg = amount * daily_roi_avg / Decimal("100")
    daily_max = amount * daily_roi_max / Decimal("100")

    weekly = daily_avg * 7
    monthly = daily_avg * 30
    quarterly = daily_avg * 90

    # Referral (1 partner same amount)
    ref_deposit = amount * Decimal("0.03")
    ref_daily = daily_avg * Decimal("0.03")
    ref_monthly = ref_daily * 30

    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🧮 Другая сумма"))
    builder.row(KeyboardButton(text="◀️ Назад к уровням"))

    text = f"""
🧮 *РАСЧЁТ: {format_money(amount)} USDT*
{'━' * 28}

⏰ Начисления: каждые *{period}ч* (×{int(accruals_per_day)}/день)
📊 За начисление: {format_percent(min_roi_acc)}—{format_percent(max_roi_acc)}%

{'─' * 28}
📈 *ВАША ДОХОДНОСТЬ*
{'─' * 28}

*Ежедневно (×{int(accruals_per_day)} начислений):*
├ 📉 Min: *+{format_money(daily_min)}* ({format_percent(daily_roi_min)}%)
├ 📊 Avg: *+{format_money(daily_avg)}* ({format_percent(daily_roi_avg)}%)
└ 📈 Max: *+{format_money(daily_max)}* ({format_percent(daily_roi_max)}%)

*При среднем ROI ~{format_percent(daily_roi_avg)}%/день:*
┌────────────────────────
│ 7 дней:   *+{format_money(weekly)}*
│ 30 дней:  *+{format_money(monthly)}*
│ 90 дней:  *+{format_money(quarterly)}*
└────────────────────────

{'─' * 28}
👥 *РЕФЕРАЛЬНЫЙ БОНУС*
{'─' * 28}

*1 партнёр с таким же депозитом:*
├ От депозита: *+{format_money(ref_deposit)}*
├ От дохода/день: *+{format_money(ref_daily)}*
└ В месяц: *+{format_money(ref_monthly)}*

{'─' * 28}
💰 *ИТОГО ПОТЕНЦИАЛ*
├ Свой доход: *{format_money(monthly)}*/мес
├ Рефералы: *+{format_money(ref_monthly)}*/мес
└ *ВСЕГО: {format_money(monthly + ref_monthly)}*/мес
{'━' * 28}

🚀 _Ваш капитал работает 24/7!_
    """.strip()

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=builder.as_markup(resize_keyboard=True),
    )


# ═══════════════════════════════════════════════════════════════════════════
# NAVIGATION HANDLERS
# ═══════════════════════════════════════════════════════════════════════════


@router.message(CalculatorStates.selecting_level, F.text == "🏠 Главное меню")
@router.message(CalculatorStates.custom_amount, F.text == "🏠 Главное меню")
async def back_to_main_menu(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Return to main menu."""
    await state.clear()
    user = data.get("user")
    is_admin = data.get("is_admin", False)

    from app.repositories.blacklist_repository import BlacklistRepository

    blacklist_repo = BlacklistRepository(session)
    blacklist_entry = None
    if user:
        blacklist_entry = await blacklist_repo.find_by_telegram_id(
            user.telegram_id
        )

    await message.answer(
        "🏠 Главное меню",
        reply_markup=main_menu_reply_keyboard(
            user=user,
            blacklist_entry=blacklist_entry,
            is_admin=is_admin,
        ),
    )


@router.message(CalculatorStates.selecting_level)
async def handle_calculator_other(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle other inputs in calculator state."""
    if is_menu_button(message.text or ""):
        await state.clear()
        user = data.get("user")
        is_admin = data.get("is_admin", False)

        from app.repositories.blacklist_repository import BlacklistRepository

        blacklist_repo = BlacklistRepository(session)
        blacklist_entry = None
        if user:
            blacklist_entry = await blacklist_repo.find_by_telegram_id(
                user.telegram_id
            )

        await message.answer(
            "🏠 Главное меню",
            reply_markup=main_menu_reply_keyboard(
                user=user,
                blacklist_entry=blacklist_entry,
                is_admin=is_admin,
            ),
        )
        return

    await message.answer(
        "❓ Выберите уровень из меню или нажмите «🏠 Главное меню»"
    )
