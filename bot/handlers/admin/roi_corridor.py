"""
Admin ROI Corridor Handler.

Manages ROI corridor configuration for deposit levels.
Supports two modes:
- Custom: Random rate from corridor (weighted to lower values)
- Equal: Fixed rate for all users

Allows setting for current or next session.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.roi_corridor_service import RoiCorridorService
from bot.handlers.admin.panel import handle_admin_panel_button
from bot.keyboards.reply import (
    admin_roi_applies_to_keyboard,
    admin_roi_confirmation_keyboard,
    admin_roi_corridor_menu_keyboard,
    admin_roi_level_select_keyboard,
    admin_roi_mode_select_keyboard,
    cancel_keyboard,
)
from bot.states.admin import AdminRoiCorridorStates
from bot.utils.admin_utils import clear_state_preserve_admin_token

router = Router(name="admin_roi_corridor")


async def show_level_roi_config(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    level: int,
    from_level_management: bool = False,
    **data: Any,
) -> None:
    """
    Show ROI configuration for specific level and start setup.
    
    This function is called from deposit_management when admin clicks
    "💰 Настроить коридор доходности" button.
    
    Args:
        message: Message object
        session: Database session
        state: FSM context
        level: Deposit level number (1-5)
        from_level_management: Whether called from level management screen
        data: Handler data
    """
    logger.info(f"[ROI_CORRIDOR] show_level_roi_config called for level {level}")
    
    is_admin = data.get("is_admin", False)
    if not is_admin:
        logger.warning(f"[ROI_CORRIDOR] Non-admin user tried to access ROI config")
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    # Get current ROI settings for this level
    logger.info(f"[ROI_CORRIDOR] Getting settings for level {level}")
    roi_service = RoiCorridorService(session)
    settings = await roi_service.get_corridor_config(level)
    accrual_period = await roi_service.get_accrual_period_hours()
    
    logger.info(f"[ROI_CORRIDOR] Settings: {settings}, period: {accrual_period}")
    
    mode = settings["mode"]
    mode_text = "Custom (случайный из коридора)" if mode == "custom" else "Поровну (фиксированный)"
    
    if mode == "custom":
        corridor_text = f"{settings['roi_min']}% - {settings['roi_max']}%"
    else:
        corridor_text = f"{settings['roi_fixed']}% (фиксированный)"
    
    text = f"""
💰 **Настройка коридора доходности для Уровня {level}**

📊 **Текущие настройки:**
• Режим: {mode_text}
• Коридор: {corridor_text}
• Период начисления: каждые {accrual_period} часов

**Что вы хотите сделать?**
    """.strip()
    
    # Save level to state and start configuration
    await state.update_data(level=level, from_level_management=from_level_management)
    await state.set_state(AdminRoiCorridorStates.selecting_mode)
    
    logger.info(f"[ROI_CORRIDOR] Sending mode selection keyboard for level {level}")
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_roi_mode_select_keyboard(),
    )
    
    logger.info(f"[ROI_CORRIDOR] Mode selection message sent successfully")


@router.message(F.text == "💰 Коридоры доходности")
async def show_roi_corridor_menu(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Show ROI corridor management menu.

    Args:
        message: Message object
        session: Database session
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    text = (
        "💰 **Управление коридорами доходности**\n\n"
        "Здесь вы можете настроить параметры начисления дохода "
        "для каждого уровня депозитов.\n\n"
        "**Режимы:**\n"
        "• Custom - случайный процент из коридора для каждого пользователя\n"
        "• Поровну - фиксированный процент для всех пользователей\n\n"
        "**Применение:**\n"
        "• Текущая сессия - изменения применятся к ближайшему начислению\n"
        "• Следующая сессия - изменения применятся через одно начисление\n\n"
        "Выберите действие:"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_roi_corridor_menu_keyboard(),
    )


@router.message(F.text == "💵 Настроить суммы уровней")
async def start_amount_setup(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Start level amount setup flow.

    Args:
        message: Message object
        state: FSM context
    """
    await state.set_state(AdminRoiCorridorStates.selecting_level_amount)
    await message.answer(
        "Выберите уровень для настройки суммы:",
        reply_markup=admin_roi_level_select_keyboard(),
    )


from bot.utils.admin_utils import clear_state_preserve_admin_token


@router.message(AdminRoiCorridorStates.selecting_level_amount)
async def process_level_amount_selection(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Process level selection for amount change.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    if message.text == "👑 Админ-панель":
        await clear_state_preserve_admin_token(state)
        await handle_admin_panel_button(message, session, **data)
        return

    if message.text == "◀️ Отмена":
        await clear_state_preserve_admin_token(state)
        await show_roi_corridor_menu(message, session, **data)
        return

    # Extract level number
    try:
        level = int(message.text.split()[-1])
        if level < 1 or level > 5:
            raise ValueError
    except Exception:
        await message.answer(
            "❌ Неверный уровень. Выберите от 1 до 5.",
            reply_markup=admin_roi_level_select_keyboard(),
        )
        return

    # Get current amount
    from app.repositories.deposit_level_version_repository import (
        DepositLevelVersionRepository,
    )
    version_repo = DepositLevelVersionRepository(session)
    current_version = await version_repo.get_current_version(level)
    
    if current_version:
        current_amount = f"{current_version.amount} USDT"
    else:
        current_amount = "Не настроен"

    await state.update_data(level=level, current_amount=current_amount)
    await state.set_state(AdminRoiCorridorStates.setting_level_amount)
    
    await message.answer(
        f"**Уровень {level} выбран.**\n"
        f"Текущая сумма: **{current_amount}**\n\n"
        "Введите новую сумму в USDT (например: `100`):",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdminRoiCorridorStates.setting_level_amount)
async def process_amount_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Process amount input.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await show_roi_corridor_menu(message, session, **data)
        return

    try:
        amount = Decimal(message.text.strip())
        if amount <= 0:
            raise ValueError("Must be positive")
    except Exception:
        await message.answer(
            "❌ Неверный формат. Введите положительное число (например: `100`):",
        )
        return

    state_data = await state.get_data()
    level = state_data.get("level")
    current_amount = state_data.get("current_amount")

    await state.update_data(new_amount=float(amount))
    await state.set_state(AdminRoiCorridorStates.confirming_level_amount)

    await message.answer(
        f"⚠️ **Подтверждение изменения суммы**\n\n"
        f"**Уровень:** {level}\n"
        f"**Текущая сумма:** {current_amount}\n"
        f"**Новая сумма:** {amount} USDT\n\n"
        "❗️ **ВНИМАНИЕ:**\n"
        "Будет создана новая версия уровня. Старые депозиты продолжат работать "
        "на прежних условиях. Новые депозиты потребуют новую сумму.\n\n"
        "Подтвердить?",
        parse_mode="Markdown",
        reply_markup=admin_roi_confirmation_keyboard(),
    )


@router.message(AdminRoiCorridorStates.confirming_level_amount)
async def process_amount_confirmation(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Process amount change confirmation.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    if "Нет" in message.text or "отменить" in message.text.lower():
        await clear_state_preserve_admin_token(state)
        await message.answer("❌ Изменения отменены.")
        await show_roi_corridor_menu(message, session, **data)
        return

    if "Да" not in message.text and "применить" not in message.text.lower():
        await message.answer(
            "❌ Неверный ответ. Выберите из предложенных вариантов.",
            reply_markup=admin_roi_confirmation_keyboard(),
        )
        return

    state_data = await state.get_data()
    level = state_data.get("level")
    amount = Decimal(str(state_data.get("new_amount")))
    admin_id = data.get("admin_id")

    if not level or not amount or not admin_id:
        await clear_state_preserve_admin_token(state)
        await message.answer("❌ Ошибка: данные потеряны")
        return

    # Call service to update amount (create new version)
    corridor_service = RoiCorridorService(session)
    success, error = await corridor_service.set_level_amount(
        level=level,
        amount=amount,
        admin_id=admin_id,
    )

    if success:
        await message.answer(
            f"✅ **Сумма успешно обновлена!**\n\n"
            f"**Уровень:** {level}\n"
            f"**Новая сумма:** {amount} USDT\n\n"
            "Изменения вступят в силу для новых депозитов.",
            parse_mode="Markdown",
        )
        
        # Notify other admins? Maybe later.
        
    else:
        await message.answer(f"❌ Ошибка: {error}")

    await clear_state_preserve_admin_token(state)
    await show_roi_corridor_menu(message, session, **data)


@router.message(F.text == "⚙️ Настроить коридоры")
async def start_corridor_setup(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Start corridor setup flow.

    Args:
        message: Message object
        state: FSM context
    """
    await state.set_state(AdminRoiCorridorStates.selecting_level)
    await message.answer(
        "Выберите уровень для настройки:",
        reply_markup=admin_roi_level_select_keyboard(),
    )


@router.message(AdminRoiCorridorStates.selecting_level)
async def process_level_selection(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Process level selection.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    if message.text == "👑 Админ-панель":
        await clear_state_preserve_admin_token(state)
        await handle_admin_panel_button(message, session, **data)
        return

    if message.text == "◀️ Отмена":
        await clear_state_preserve_admin_token(state)
        await show_roi_corridor_menu(message, session, **data)
        return

    # Extract level number
    try:
        level = int(message.text.split()[-1])
        if level < 1 or level > 5:
            raise ValueError
    except Exception:
        await message.answer(
            "❌ Неверный уровень. Выберите от 1 до 5.",
            reply_markup=admin_roi_level_select_keyboard(),
        )
        return

    await state.update_data(level=level)
    await state.set_state(AdminRoiCorridorStates.selecting_mode)
    await message.answer(
        f"**Уровень {level} выбран.**\n\nВыберите режим начисления:",
        parse_mode="Markdown",
        reply_markup=admin_roi_mode_select_keyboard(),
    )


@router.message(AdminRoiCorridorStates.selecting_mode)
async def process_mode_selection(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Process mode selection.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    logger.info(f"[ROI_CORRIDOR] process_mode_selection called, text: {message.text}")
    
    if message.text == "👑 Админ-панель":
        await clear_state_preserve_admin_token(state)
        await handle_admin_panel_button(message, session, **data)
        return

    if message.text == "◀️ Отмена":
        logger.info(f"[ROI_CORRIDOR] User cancelled mode selection")
        await clear_state_preserve_admin_token(state)
        await show_roi_corridor_menu(message, session, **data)
        return

    if "Custom" in message.text:
        mode = "custom"
        mode_text = "Custom (случайный из коридора)"
        logger.info(f"[ROI_CORRIDOR] Selected Custom mode")
    elif "Поровну" in message.text:
        mode = "equal"
        mode_text = "Поровну (фиксированный для всех)"
        logger.info(f"[ROI_CORRIDOR] Selected Equal mode")
    else:
        logger.warning(f"[ROI_CORRIDOR] Invalid mode selection: {message.text}")
        await message.answer(
            "❌ Неверный режим. Выберите из предложенных вариантов.",
            reply_markup=admin_roi_mode_select_keyboard(),
        )
        return

    await state.update_data(mode=mode, mode_text=mode_text)

    # Immediately ask for values based on mode
    if mode == "custom":
        await state.set_state(AdminRoiCorridorStates.entering_min)
        await message.answer(
            f"**Режим:** {mode_text}\n\n"
            "**Шаг 1/4: Введите минимальный процент коридора**\n\n"
            "Например: `0.8` (для 0.8% в период)\n\n"
            "Это нижняя граница случайного процента.",
            parse_mode="Markdown",
        )
    else:
        await state.set_state(AdminRoiCorridorStates.entering_fixed)
        await message.answer(
            f"**Режим:** {mode_text}\n\n"
            "**Шаг 1/3: Введите фиксированный процент для всех**\n\n"
            "Например: `5.5` (для 5.5% в период)\n\n"
            "Все пользователи будут получать одинаковый процент.",
            parse_mode="Markdown",
        )


@router.message(AdminRoiCorridorStates.selecting_applies_to)
async def process_applies_to(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Process application scope selection.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    if message.text == "👑 Админ-панель":
        await clear_state_preserve_admin_token(state)
        await handle_admin_panel_button(message, session, **data)
        return

    if message.text == "◀️ Отмена":
        await clear_state_preserve_admin_token(state)
        await show_roi_corridor_menu(message, session, **data)
        return

    if "текущей" in message.text:
        applies_to = "current"
        applies_text = "текущей сессии (ближайшее начисление)"
    elif "следующей" in message.text:
        applies_to = "next"
        applies_text = "следующей сессии (через одно начисление)"
    else:
        await message.answer(
            "❌ Неверный выбор. Выберите из предложенных вариантов.",
            reply_markup=admin_roi_applies_to_keyboard(),
        )
        return

    await state.update_data(applies_to=applies_to, applies_text=applies_text)

    # After selecting when to apply, ask for optional reason/comment
    await state.set_state(AdminRoiCorridorStates.entering_reason)
    await message.answer(
        "📝 **Шаг 3: Введите причину изменения (опционально)**\n\n"
        "Пример: `Экстренное снижение доходности` или `Плановое повышение`\n\n"
        "Если не хотите указывать причину, отправьте `Пропустить`.",
        parse_mode="Markdown",
    )


@router.message(AdminRoiCorridorStates.entering_reason)
async def process_reason_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Process optional human-readable reason for corridor change.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    raw_text = (message.text or "").strip()
    if raw_text.lower() in {"пропустить", "skip"}:
        reason = None
    else:
        reason = raw_text or None

    await state.update_data(reason=reason)

    # After capturing reason, show confirmation summary
    await show_confirmation(message, state, session, data)


@router.message(AdminRoiCorridorStates.entering_min)
async def process_min_input(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Process minimum percentage input.

    Args:
        message: Message object
        state: FSM context
    """
    try:
        roi_min = Decimal(message.text.strip())
        if roi_min < 0:
            raise ValueError("Negative value")
    except Exception:
        await message.answer(
            "❌ Неверный формат. Введите число (например: `0.8`):",
            parse_mode="Markdown",
        )
        return

    # Convert Decimal to float for JSON serialization in FSM state
    await state.update_data(roi_min=float(roi_min))
    await state.set_state(AdminRoiCorridorStates.entering_max)
    await message.answer(
        f"**Минимум:** {roi_min}%\n\n"
        "**Введите максимальный процент коридора**\n\n"
        "Например: `10` (для 10% в период)\n\n"
        "Это верхняя граница случайного процента.",
        parse_mode="Markdown",
    )


@router.message(AdminRoiCorridorStates.entering_max)
async def process_max_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Process maximum percentage input.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    try:
        roi_max = Decimal(message.text.strip())
        if roi_max < 0:
            raise ValueError("Negative value")
    except Exception:
        await message.answer(
            "❌ Неверный формат. Введите число (например: `10`):",
            parse_mode="Markdown",
        )
        return

    state_data = await state.get_data()
    roi_min = Decimal(str(state_data["roi_min"]))  # Convert back from float

    if roi_max <= roi_min:
        await message.answer(
            f"❌ Максимум ({roi_max}%) должен быть больше "
            f"минимума ({roi_min}%).\n\n"
            "Введите максимальный процент заново:",
        )
        return

    # Convert Decimal to float for JSON serialization in FSM state
    await state.update_data(roi_max=float(roi_max))
    
    # After entering corridor, ask when to apply
    await state.set_state(AdminRoiCorridorStates.selecting_applies_to)
    await message.answer(
        f"**Коридор:** {roi_min}% - {roi_max}%\n\n"
        "**Шаг 2/4: Когда применить изменения?**\n\n"
        "⚡️ **Текущая сессия** - изменения применятся к ближайшему "
        "начислению всех пользователей (в течение периода начисления)\n\n"
        "⏭ **Следующая сессия** - изменения применятся через одно "
        "начисление",
        parse_mode="Markdown",
        reply_markup=admin_roi_applies_to_keyboard(),
    )


@router.message(AdminRoiCorridorStates.entering_fixed)
async def process_fixed_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Process fixed percentage input.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    try:
        roi_fixed = Decimal(message.text.strip())
        if roi_fixed < 0:
            raise ValueError("Negative value")
    except Exception:
        await message.answer(
            "❌ Неверный формат. Введите число (например: `5.5`):",
            parse_mode="Markdown",
        )
        return

    # Convert Decimal to float for JSON serialization in FSM state
    await state.update_data(roi_fixed=float(roi_fixed))
    
    # After entering fixed rate, ask when to apply
    await state.set_state(AdminRoiCorridorStates.selecting_applies_to)
    await message.answer(
        f"**Фиксированный процент:** {roi_fixed}%\n\n"
        "**Шаг 2/3: Когда применить изменения?**\n\n"
        "⚡️ **Текущая сессия** - изменения применятся к ближайшему "
        "начислению всех пользователей (в течение периода начисления)\n\n"
        "⏭ **Следующая сессия** - изменения применятся через одно "
        "начисление",
        parse_mode="Markdown",
        reply_markup=admin_roi_applies_to_keyboard(),
    )


async def show_confirmation(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    data: dict,
) -> None:
    """
    Show confirmation screen with settings summary.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    state_data = await state.get_data()
    level = state_data["level"]
    mode = state_data["mode"]
    mode_text = state_data["mode_text"]
    applies_to = state_data["applies_to"]
    applies_text = state_data["applies_text"]

    if mode == "custom":
        roi_min = state_data["roi_min"]
        roi_max = state_data["roi_max"]
        config_text = f"**Коридор:** {roi_min}% - {roi_max}%"
    else:
        roi_fixed = state_data["roi_fixed"]
        config_text = f"**Фиксированный:** {roi_fixed}%"

    reason = state_data.get("reason")

    # Validate and get warnings
    corridor_service = RoiCorridorService(session)
    warning = ""

    if mode == "custom":
        # Convert float back to Decimal for validation
        roi_min_decimal = Decimal(str(state_data["roi_min"]))
        roi_max_decimal = Decimal(str(state_data["roi_max"]))
        needs_confirm, warning_msg = (
            await corridor_service.validate_corridor_settings(
                roi_min_decimal, roi_max_decimal
            )
        )
        if needs_confirm and warning_msg:
            warning = f"\n\n{warning_msg}\n\n⚠️ **Требуется подтверждение!**"
    else:
        roi_fixed_float = state_data["roi_fixed"]
        if roi_fixed_float < 0.5 or roi_fixed_float > 20:
            warning = (
                f"\n\n⚠️ **ПРЕДУПРЕЖДЕНИЕ:** "
                f"Экстремальное значение: {roi_fixed_float}%\n"
                "(Рекомендуется: 0.5% - 20%)\n\n"
                "⚠️ **Требуется подтверждение!**"
            )

    reason_block = ""
    if reason:
        reason_block = f"\n**Причина:** {reason}"

    text = (
        "📋 **Подтверждение настроек**\n\n"
        f"**Уровень:** {level}\n"
        f"**Режим:** {mode_text}\n"
        f"{config_text}\n"
        f"**Применить к:** {applies_text}"
        f"{reason_block}"
        f"{warning}\n\n"
        "Подтвердите изменения:"
    )

    await state.set_state(AdminRoiCorridorStates.confirming)
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_roi_confirmation_keyboard(),
    )


@router.message(AdminRoiCorridorStates.confirming)
async def process_confirmation(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Process confirmation.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    if "Нет" in message.text or "отменить" in message.text.lower():
        await clear_state_preserve_admin_token(state)
        await message.answer("❌ Изменения отменены.")
        await show_roi_corridor_menu(message, session, **data)
        return

    if "Да" not in message.text and "применить" not in message.text.lower():
        await message.answer(
            "❌ Неверный ответ. Выберите из предложенных вариантов.",
            reply_markup=admin_roi_confirmation_keyboard(),
        )
        return

    state_data = await state.get_data()
    admin_id = data.get("admin_id")

    if not admin_id:
        await clear_state_preserve_admin_token(state)
        await message.answer("❌ Ошибка: admin_id не найден")
        return

    corridor_service = RoiCorridorService(session)

    # Convert float back to Decimal for service call
    roi_min_val = state_data.get("roi_min")
    roi_max_val = state_data.get("roi_max")
    roi_fixed_val = state_data.get("roi_fixed")
    reason = state_data.get("reason")

    success, error = await corridor_service.set_corridor(
        level=state_data["level"],
        mode=state_data["mode"],
        roi_min=Decimal(str(roi_min_val)) if roi_min_val is not None else None,
        roi_max=Decimal(str(roi_max_val)) if roi_max_val is not None else None,
        roi_fixed=Decimal(str(roi_fixed_val)) if roi_fixed_val is not None else None,
        admin_id=admin_id,
        applies_to=state_data["applies_to"],
        reason=reason,
    )

    if success:
        level = state_data["level"]
        mode_text = state_data["mode_text"]
        applies_text = state_data["applies_text"]

        if state_data["mode"] == "custom":
            config_text = (
                f"{state_data['roi_min']}% - {state_data['roi_max']}%"
            )
        else:
            config_text = f"{state_data['roi_fixed']}%"

        await message.answer(
            f"✅ **Настройки успешно применены!**\n\n"
            f"**Уровень:** {level}\n"
            f"**Режим:** {mode_text}\n"
            f"**Значение:** {config_text}\n"
            f"**Применено к:** {applies_text}",
            parse_mode="Markdown",
        )

        # Notify other admins
        await _notify_other_admins(
            session, admin_id, level, mode_text, config_text, applies_text
        )

        logger.info(
            "Corridor settings updated",
            extra={
                "level": level,
                "mode": state_data["mode"],
                "applies_to": state_data["applies_to"],
                "admin_id": admin_id,
            },
        )
        
        # Check if we should redirect back to level management
        if state_data.get("from_level_management"):
            # Import here to avoid circular dependency
            from bot.handlers.admin.deposit_management import show_level_actions
            
            # We need to set the managing_level in state for show_level_actions
            # But wait, show_level_actions expects a Message with "Уровень X"
            # Or we can call it directly if we mock the message?
            # Better: simulate what show_level_actions does or call a helper.
            
            # Actually, show_level_actions reads level from message text.
            # Let's create a helper or set state and show menu.
            
            # We can just call show_level_actions, but we need to ensure state is clean
            # and has managing_level if needed? No, show_level_actions sets managing_level based on message.
            # But we don't have a message with "Уровень X".
            
            # Let's manually set state and show the actions menu.            
            from bot.handlers.admin.deposit_management import show_level_actions_for_level
            
            await clear_state_preserve_admin_token(state)
            await show_level_actions_for_level(message, session, state, level, **data)
            return

    else:
        await message.answer(f"❌ Ошибка: {error}")

    await clear_state_preserve_admin_token(state)
    await show_roi_corridor_menu(message, session, **data)


@router.message(F.text == "📊 Текущие настройки")
async def show_current_settings(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Show current corridor settings for all levels.

    Args:
        message: Message object
        session: Database session
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    corridor_service = RoiCorridorService(session)

    text = "📊 **Текущие настройки коридоров:**\n\n"

    for level in range(1, 6):
        config = await corridor_service.get_corridor_config(level)
        mode_text = (
            "Custom" if config["mode"] == "custom" else "Поровну"
        )

        text += f"**{level}️⃣ Уровень {level}:** {mode_text}\n"

        if config["mode"] == "custom":
            text += f"   Коридор: {config['roi_min']}% - {config['roi_max']}%\n"
        else:
            text += f"   Фиксированный: {config['roi_fixed']}%\n"

        text += "\n"

    period = await corridor_service.get_accrual_period_hours()
    text += f"⏱ **Период начисления:** {period} часов"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_roi_corridor_menu_keyboard(),
    )


@router.message(F.text == "📜 История изменений")
async def start_history_view(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Start history viewing flow.

    Args:
        message: Message object
        state: FSM context
    """
    await state.set_state(AdminRoiCorridorStates.viewing_history_level)
    await message.answer(
        "Выберите уровень для просмотра истории изменений:",
        reply_markup=admin_roi_level_select_keyboard(),
    )


@router.message(AdminRoiCorridorStates.viewing_history_level)
async def show_level_history(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Show history for selected level.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    if message.text == "👑 Админ-панель":
        await clear_state_preserve_admin_token(state)
        await handle_admin_panel_button(message, session, **data)
        return

    if message.text == "◀️ Отмена":
        await clear_state_preserve_admin_token(state)
        await show_roi_corridor_menu(message, session, **data)
        return

    # Extract level number
    try:
        level = int(message.text.split()[-1])
        if level < 1 or level > 5:
            raise ValueError
    except Exception:
        await message.answer(
            "❌ Неверный уровень. Выберите от 1 до 5.",
            reply_markup=admin_roi_level_select_keyboard(),
        )
        return

    corridor_service = RoiCorridorService(session)
    history = await corridor_service.history_repo.get_history_for_level(
        level, limit=20
    )

    if not history:
        await message.answer(
            f"📜 История изменений для уровня {level} пуста.",
            reply_markup=admin_roi_corridor_menu_keyboard(),
        )
        await clear_state_preserve_admin_token(state)
        return

    text = f"📜 **История изменений - Уровень {level}**\n\n"

    # Lazy import to avoid circular dependencies
    from app.repositories.admin_repository import AdminRepository

    admin_repo = AdminRepository(session)

    for record in history[:10]:
        mode_text = "Custom" if record.mode == "custom" else "Поровну"
        applies_text = (
            "текущая" if record.applies_to == "current" else "следующая"
        )

        if record.mode == "custom":
            config_text = f"{record.roi_min}% - {record.roi_max}%"
        else:
            config_text = f"{record.roi_fixed}%"

        # Build admin info: @username (ID: 123) or "Система"
        if record.changed_by_admin_id:
            admin = await admin_repo.get_by_id(record.changed_by_admin_id)
            if admin and admin.username:
                admin_label = f"@{admin.username} (ID: {admin.telegram_id})"
            elif admin:
                admin_label = f"Admin (ID: {admin.telegram_id})"
            else:
                admin_label = f"Admin ID: {record.changed_by_admin_id}"
        else:
            admin_label = "Система"

        reason = record.reason
        reason_block = f"   💬 Причина: {reason}\n" if reason else ""

        text += (
            f"📅 {record.changed_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"   Режим: {mode_text}\n"
            f"   Значение: {config_text}\n"
            f"   Применено к: {applies_text}\n"
            f"   Изменил: {admin_label}\n"
            f"{reason_block}\n"
        )

    if len(history) > 10:
        text += f"... и еще {len(history) - 10} записей"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_roi_corridor_menu_keyboard(),
    )
    await clear_state_preserve_admin_token(state)


@router.message(F.text == "⏱ Настроить период начисления")
async def start_period_setup(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Start period setup flow.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    corridor_service = RoiCorridorService(session)
    current_period = await corridor_service.get_accrual_period_hours()

    await state.set_state(AdminRoiCorridorStates.setting_period)
    await message.answer(
        f"⏱ **Настройка периода начисления**\n\n"
        f"**Текущий период:** {current_period} часов\n\n"
        "Введите новый период в часах (от 1 до 24):\n\n"
        "Например: `6` (для начисления каждые 6 часов)\n\n"
        "⚠️ **Важно:** Период применяется индивидуально для каждого "
        "пользователя от момента создания его депозита.",
        parse_mode="Markdown",
    )


@router.message(AdminRoiCorridorStates.setting_period)
async def process_period_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Process period input.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    try:
        hours = int(message.text.strip())
        if hours < 1 or hours > 24:
            raise ValueError("Out of range")
    except Exception:
        await message.answer(
            "❌ Неверный формат. Введите целое число от 1 до 24:",
        )
        return

    # Save to state and show confirmation
    await state.update_data(new_period_hours=hours)
    await state.set_state(AdminRoiCorridorStates.confirming_period)

    await message.answer(
        f"⚠️ **Подтверждение изменений**\n\n"
        f"Новый период начисления: **{hours} часов**\n\n"
        "❗️ **ВНИМАНИЕ:**\n"
        "Изменения применятся к следующему циклу начисления для всех депозитов!\n\n"
        "Подтвердить?",
        parse_mode="Markdown",
        reply_markup=admin_roi_confirmation_keyboard(),
    )


@router.message(AdminRoiCorridorStates.confirming_period)
async def process_period_confirmation(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Process period change confirmation.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    if "Нет" in message.text or "отменить" in message.text.lower():
        await clear_state_preserve_admin_token(state)
        await message.answer("❌ Изменения отменены.")
        await show_roi_corridor_menu(message, session, **data)
        return

    if "Да" not in message.text and "применить" not in message.text.lower():
        await message.answer(
            "❌ Неверный ответ. Выберите из предложенных вариантов.",
            reply_markup=admin_roi_confirmation_keyboard(),
        )
        return

    state_data = await state.get_data()
    hours = state_data.get("new_period_hours")
    admin_id = data.get("admin_id")

    if not hours or not admin_id:
        await clear_state_preserve_admin_token(state)
        await message.answer("❌ Ошибка: данные потеряны")
        return

    corridor_service = RoiCorridorService(session)
    success, error = await corridor_service.set_accrual_period_hours(
        hours, admin_id
    )

    if success:
        await message.answer(
            f"✅ **Период начисления обновлён!**\n\n"
            f"Новый период: {hours} часов\n\n"
            "Изменения вступят в силу при следующем автоматическом начислении.",
            parse_mode="Markdown",
        )

        # Notify other admins
        await _notify_other_admins_period(session, admin_id, hours)

        logger.info(
            "Accrual period updated",
            extra={"hours": hours, "admin_id": admin_id},
        )
    else:
        await message.answer(f"❌ Ошибка: {error}")

    await clear_state_preserve_admin_token(state)
    await show_roi_corridor_menu(message, session, **data)


@router.message(F.text == "◀️ Назад в управление депозитами")
async def back_to_deposit_management(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Return to deposit management menu.

    Args:
        message: Message object
        state: FSM context
        session: Database session
        data: Handler data
    """
    await clear_state_preserve_admin_token(state)
    from bot.handlers.admin.deposit_management import (
        show_deposit_management_menu,
    )

    await show_deposit_management_menu(message, session, **data)


async def _notify_other_admins(
    session: AsyncSession,
    admin_id: int,
    level: int,
    mode_text: str,
    config_text: str,
    applies_text: str,
) -> None:
    """
    Notify other admins about corridor change.

    Args:
        session: Database session
        admin_id: Admin who made the change
        level: Changed level
        mode_text: Mode description
        config_text: Configuration description
        applies_text: Application scope description
    """
    try:
        from app.repositories.admin_repository import AdminRepository

        admin_repo = AdminRepository(session)
        all_admins = await admin_repo.get_extended_admins()

        notification_text = (
            "🔔 **Изменены настройки коридора доходности**\n\n"
            f"**Уровень:** {level}\n"
            f"**Режим:** {mode_text}\n"
            f"**Значение:** {config_text}\n"
            f"**Применено к:** {applies_text}\n"
            f"**Изменил:** Admin ID {admin_id}"
        )

        for admin in all_admins:
            if admin.id != admin_id:
                try:
                    from bot.utils.notification import send_telegram_message

                    await send_telegram_message(
                        admin.telegram_id, notification_text
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to notify admin {admin.id}: {e}",
                        extra={"admin_id": admin.id, "error": str(e)},
                    )
    except Exception as e:
        logger.error(
            f"Failed to notify admins: {e}",
            extra={"error": str(e)},
        )


async def _notify_other_admins_period(
    session: AsyncSession,
    admin_id: int,
    hours: int,
) -> None:
    """
    Notify other admins about period change.

    Args:
        session: Database session
        admin_id: Admin who made the change
        hours: New period in hours
    """
    try:
        from app.repositories.admin_repository import AdminRepository

        admin_repo = AdminRepository(session)
        all_admins = await admin_repo.get_extended_admins()

        notification_text = (
            "🔔 **Изменен период начисления**\n\n"
            f"**Новый период:** {hours} часов\n"
            f"**Изменил:** Admin ID {admin_id}"
        )

        for admin in all_admins:
            if admin.id != admin_id:
                try:
                    from bot.utils.notification import send_telegram_message

                    await send_telegram_message(
                        admin.telegram_id, notification_text
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to notify admin {admin.id}: {e}",
                        extra={"admin_id": admin.id, "error": str(e)},
                    )
    except Exception as e:
        logger.error(
            f"Failed to notify admins: {e}",
            extra={"error": str(e)},
        )

