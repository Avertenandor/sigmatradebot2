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
from bot.keyboards.reply import (
    admin_roi_applies_to_keyboard,
    admin_roi_confirmation_keyboard,
    admin_roi_corridor_menu_keyboard,
    admin_roi_level_select_keyboard,
    admin_roi_mode_select_keyboard,
)
from bot.states.admin import AdminRoiCorridorStates

router = Router(name="admin_roi_corridor")


async def show_level_roi_config(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    level: int,
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
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    # Get current ROI settings for this level
    roi_service = RoiCorridorService(session)
    settings = await roi_service.get_corridor_config(level)
    accrual_period = await roi_service.get_accrual_period_hours()
    
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
    await state.update_data(level=level)
    await state.set_state(AdminRoiCorridorStates.selecting_mode)
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_roi_mode_select_keyboard(),
    )


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
    if message.text == "◀️ Отмена":
        await state.clear()
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
    if message.text == "◀️ Отмена":
        await state.clear()
        await show_roi_corridor_menu(message, session, **data)
        return

    if "Custom" in message.text:
        mode = "custom"
        mode_text = "Custom (случайный из коридора)"
    elif "Поровну" in message.text:
        mode = "equal"
        mode_text = "Поровну (фиксированный для всех)"
    else:
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
    if message.text == "◀️ Отмена":
        await state.clear()
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
    
    # After selecting when to apply, show confirmation
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

    await state.update_data(roi_min=roi_min)
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
    roi_min = state_data["roi_min"]

    if roi_max <= roi_min:
        await message.answer(
            f"❌ Максимум ({roi_max}%) должен быть больше "
            f"минимума ({roi_min}%).\n\n"
            "Введите максимальный процент заново:",
        )
        return

    await state.update_data(roi_max=roi_max)
    
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

    await state.update_data(roi_fixed=roi_fixed)
    
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

    # Validate and get warnings
    corridor_service = RoiCorridorService(session)
    warning = ""

    if mode == "custom":
        needs_confirm, warning_msg = (
            await corridor_service.validate_corridor_settings(
                state_data["roi_min"], state_data["roi_max"]
            )
        )
        if needs_confirm and warning_msg:
            warning = f"\n\n{warning_msg}\n\n⚠️ **Требуется подтверждение!**"
    else:
        roi_fixed = state_data["roi_fixed"]
        if roi_fixed < Decimal("0.5") or roi_fixed > Decimal("20"):
            warning = (
                f"\n\n⚠️ **ПРЕДУПРЕЖДЕНИЕ:** "
                f"Экстремальное значение: {roi_fixed}%\n"
                "(Рекомендуется: 0.5% - 20%)\n\n"
                "⚠️ **Требуется подтверждение!**"
            )

    text = (
        "📋 **Подтверждение настроек**\n\n"
        f"**Уровень:** {level}\n"
        f"**Режим:** {mode_text}\n"
        f"{config_text}\n"
        f"**Применить к:** {applies_text}"
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
        await state.clear()
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
        await state.clear()
        await message.answer("❌ Ошибка: admin_id не найден")
        return

    corridor_service = RoiCorridorService(session)

    success, error = await corridor_service.set_corridor(
        level=state_data["level"],
        mode=state_data["mode"],
        roi_min=state_data.get("roi_min"),
        roi_max=state_data.get("roi_max"),
        roi_fixed=state_data.get("roi_fixed"),
        admin_id=admin_id,
        applies_to=state_data["applies_to"],
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
    else:
        await message.answer(f"❌ Ошибка: {error}")

    await state.clear()
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
    if message.text == "◀️ Отмена":
        await state.clear()
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
        await state.clear()
        return

    text = f"📜 **История изменений - Уровень {level}**\n\n"

    for record in history[:10]:
        mode_text = "Custom" if record.mode == "custom" else "Поровну"
        applies_text = (
            "текущая" if record.applies_to == "current" else "следующая"
        )

        if record.mode == "custom":
            config_text = f"{record.roi_min}% - {record.roi_max}%"
        else:
            config_text = f"{record.roi_fixed}%"

        admin_info = (
            f"Admin ID: {record.changed_by_admin_id}"
            if record.changed_by_admin_id
            else "Система"
        )

        text += (
            f"📅 {record.changed_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"   Режим: {mode_text}\n"
            f"   Значение: {config_text}\n"
            f"   Применено к: {applies_text}\n"
            f"   Изменил: {admin_info}\n\n"
        )

    if len(history) > 10:
        text += f"... и еще {len(history) - 10} записей"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_roi_corridor_menu_keyboard(),
    )
    await state.clear()


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

    admin_id = data.get("admin_id")
    if not admin_id:
        await state.clear()
        await message.answer("❌ Ошибка: admin_id не найден")
        return

    corridor_service = RoiCorridorService(session)
    success, error = await corridor_service.set_accrual_period_hours(
        hours, admin_id
    )

    if success:
        await message.answer(
            f"✅ **Период начисления обновлен!**\n\n"
            f"**Новый период:** {hours} часов\n\n"
            "Изменения применятся к новым начислениям.",
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

    await state.clear()
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
    await state.clear()
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
        all_admins = await admin_repo.get_all()

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
        all_admins = await admin_repo.get_all()

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

