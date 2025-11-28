"""
Admin Deposit Management Handler.

Provides comprehensive deposit management functionality for admins:
- Statistics and analytics
- Level management (enable/disable)
- Pending deposits review
- User deposit search
- ROI statistics
"""

from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deposit import Deposit
from app.models.enums import TransactionStatus
from app.repositories.deposit_level_version_repository import (
    DepositLevelVersionRepository,
)
from app.repositories.deposit_repository import DepositRepository
from app.repositories.global_settings_repository import GlobalSettingsRepository
from app.services.deposit_service import DepositService
from bot.keyboards.reply import (
    admin_deposit_management_keyboard,
    admin_deposit_levels_keyboard,
    admin_deposit_level_actions_keyboard,
    admin_keyboard,
    cancel_keyboard,
)
from bot.states.admin import AdminDepositManagementStates
from bot.utils.formatters import format_usdt

router = Router(name="admin_deposit_management")


@router.message(F.text == "💰 Управление депозитами")
async def show_deposit_management_menu(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Show deposit management main menu.
    
    Args:
        message: Message object
        session: Database session
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    text = """
💰 **Управление депозитами**

Выберите действие:
    """.strip()
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_deposit_management_keyboard(),
    )


@router.message(F.text == "📊 Статистика по депозитам")
async def show_deposit_statistics(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Show comprehensive deposit statistics.
    
    Args:
        message: Message object
        session: Database session
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    deposit_repo = DepositRepository(session)
    
    # Get total statistics
    stmt = select(
        func.count(Deposit.id).label("total"),
        func.count(Deposit.id).filter(
            Deposit.status == TransactionStatus.CONFIRMED.value
        ).label("active"),
        func.count(Deposit.id).filter(
            Deposit.is_roi_completed == True  # noqa: E712
        ).label("completed"),
        func.count(Deposit.id).filter(
            Deposit.status == TransactionStatus.PENDING.value
        ).label("pending"),
    )
    
    result = await session.execute(stmt)
    stats = result.one()
    
    # Get statistics by level
    level_stats = []
    for level_num in range(1, 6):
        stmt_level = select(
            func.count(Deposit.id).label("count"),
            func.sum(Deposit.amount).label("total_amount"),
        ).where(
            Deposit.level == level_num,
            Deposit.status == TransactionStatus.CONFIRMED.value,
        )
        
        result_level = await session.execute(stmt_level)
        level_data = result_level.one()
        
        count = level_data.count or 0
        total_amount = level_data.total_amount or Decimal("0")
        
        level_stats.append((level_num, count, total_amount))
    
    # Calculate grand total
    grand_total = sum(amount for _, _, amount in level_stats)
    
    # Format message
    text = f"""
📊 **Статистика депозитов**

**Общая информация:**
Всего депозитов: {stats.total}
Активных: {stats.active}
Завершенных: {stats.completed}
Pending: {stats.pending}

**По уровням:**
"""
    
    for level_num, count, total_amount in level_stats:
        emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"][level_num - 1]
        text += f"{emoji} Уровень {level_num}: {count} депозитов ({format_usdt(total_amount)})\n"
    
    text += f"\n💰 **Общая сумма:** {format_usdt(grand_total)}"
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_deposit_management_keyboard(),
    )


@router.message(F.text == "🔍 Найти депозиты пользователя")
async def start_search_user_deposits(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Start user deposit search flow.
    
    Args:
        message: Message object
        state: FSM context
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    await state.set_state(AdminDepositManagementStates.searching_user_deposits)
    
    await message.answer(
        "🔍 **Поиск депозитов пользователя**\n\n"
        "Введите Telegram ID пользователя:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


from bot.utils.admin_utils import clear_state_preserve_admin_token


@router.message(AdminDepositManagementStates.searching_user_deposits)
async def process_user_id_for_deposits(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Process user ID and show their deposits.
    
    Args:
        message: Message object
        session: Database session
        state: FSM context
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return
    
    # Check for cancel
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "❌ Поиск отменён.",
            reply_markup=admin_deposit_management_keyboard(),
        )
        return
    
    # Check if menu button
    from bot.utils.menu_buttons import is_menu_button
    
    if message.text and is_menu_button(message.text):
        await clear_state_preserve_admin_token(state)
        return
    
    # Parse Telegram ID
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Неверный формат! Введите числовой Telegram ID.",
            reply_markup=cancel_keyboard(),
        )
        return
    
    # Find user
    from app.repositories.user_repository import UserRepository
    
    user_repo = UserRepository(session)
    user = await user_repo.get_by(telegram_id=telegram_id)
    
    if not user:
        await message.answer(
            f"❌ Пользователь с ID `{telegram_id}` не найден.",
            parse_mode="Markdown",
            reply_markup=admin_deposit_management_keyboard(),
        )
        await clear_state_preserve_admin_token(state)
        return
    
    # Get user's deposits
    deposit_repo = DepositRepository(session)
    deposits = await deposit_repo.find_by(user_id=user.id)
    
    if not deposits:
        await message.answer(
            f"ℹ️ У пользователя `{telegram_id}` нет депозитов.",
            parse_mode="Markdown",
            reply_markup=admin_deposit_management_keyboard(),
        )
        await clear_state_preserve_admin_token(state)
        return
    
    # Format deposits
    text = f"📋 **Депозиты пользователя {telegram_id}**\n"
    text += f"Username: @{user.username or 'N/A'}\n\n"
    
    for deposit in deposits:
        status_emoji = {
            TransactionStatus.PENDING.value: "⏳",
            TransactionStatus.CONFIRMED.value: "✅",
            TransactionStatus.FAILED.value: "❌",
        }.get(deposit.status, "❓")
        
        roi_progress = ""
        if deposit.status == TransactionStatus.CONFIRMED.value:
            if deposit.is_roi_completed:
                roi_progress = " (ROI завершён)"
            else:
                percent = (
                    (deposit.roi_paid_amount / deposit.roi_cap_amount * 100)
                    if deposit.roi_cap_amount > 0
                    else 0
                )
                roi_progress = f" (ROI: {percent:.1f}%)"
        
        text += (
            f"{status_emoji} **Уровень {deposit.level}** - {format_usdt(deposit.amount)}\n"
            f"   ID: `{deposit.id}`\n"
            f"   Статус: {deposit.status}{roi_progress}\n"
            f"   Заработано: {format_usdt(deposit.roi_paid_amount)} USDT\n"
            f"   Дата: {deposit.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_deposit_management_keyboard(),
    )
    await clear_state_preserve_admin_token(state)


@router.message(F.text == "⚙️ Управление уровнями")
async def show_levels_management(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Show level management menu with current status.
    
    Args:
        message: Message object
        session: Database session
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    global_settings_repo = GlobalSettingsRepository(session)
    settings = await global_settings_repo.get_settings()
    version_repo = DepositLevelVersionRepository(session)
    
    max_level = settings.max_open_deposit_level
    
    text = f"⚙️ **Управление уровнями депозитов**\n\n"
    text += f"Максимальный открытый уровень: **{max_level}**\n\n"
    text += "**Статус уровней:**\n\n"
    
    for level_num in range(1, 6):
        current_version = await version_repo.get_current_version(level_num)
        
        if current_version:
            status = "✅ Активен" if current_version.is_active else "❌ Отключен"
            amount = format_usdt(current_version.amount)
        else:
            status = "⚠️ Не настроен"
            amount = "N/A"
        
        emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"][level_num - 1]
        text += f"{emoji} **Уровень {level_num}** ({amount}): {status}\n"
    
    text += "\n💡 Выберите уровень для управления:"
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_deposit_levels_keyboard(),
    )


async def show_level_actions_for_level(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    level: int,
    **data: Any,
) -> None:
    """
    Show actions for specific level (helper).
    
    Args:
        message: Message object
        session: Database session
        state: FSM context
        level: Level number
        data: Handler data
    """
    # Get level status
    version_repo = DepositLevelVersionRepository(session)
    current_version = await version_repo.get_current_version(level)
    
    if not current_version:
        await message.answer(
            f"⚠️ Уровень {level} не настроен в системе.",
            reply_markup=admin_deposit_levels_keyboard(),
        )
        return
    
    is_active = current_version.is_active
    
    # Save level to state
    await state.update_data(managing_level=level)
    await state.set_state(AdminDepositManagementStates.managing_level)
    
    status_text = "✅ Активен" if is_active else "❌ Отключен"
    
    text = f"""
⚙️ **Управление уровнем {level}**

Сумма: {format_usdt(current_version.amount)}
Статус: {status_text}
ROI: {current_version.roi_percent}%
ROI Cap: {current_version.roi_cap_percent}%

Выберите действие:
    """.strip()
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_deposit_level_actions_keyboard(level, is_active),
    )


@router.message(F.text.startswith("Уровень "))
async def show_level_actions(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Show actions for specific level.
    
    Args:
        message: Message object
        session: Database session
        state: FSM context
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return
    
    # Extract level number
    try:
        level = int(message.text.split()[1])
        if level < 1 or level > 5:
            raise ValueError
    except (ValueError, IndexError):
        await message.answer(
            "❌ Неверный формат уровня.",
            reply_markup=admin_deposit_levels_keyboard(),
        )
        return
    
    await show_level_actions_for_level(message, session, state, level, **data)


@router.message(F.text == "🔢 Изм. макс. уровень")
async def start_max_level_change(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Start max level change flow.
    
    Args:
        message: Message object
        session: Database session
        state: FSM context
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    global_settings_repo = GlobalSettingsRepository(session)
    settings = await global_settings_repo.get_settings()
    current_max = settings.max_open_deposit_level

    await state.set_state(AdminDepositManagementStates.setting_max_level)
    
    await message.answer(
        f"🔢 **Изменение максимального уровня**\n\n"
        f"Текущий макс. уровень: **{current_max}**\n\n"
        "Введите новое значение (1-5):\n"
        "Пользователи смогут открывать депозиты только до этого уровня включительно.",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdminDepositManagementStates.setting_max_level)
async def process_max_level_change(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Process max level input.
    
    Args:
        message: Message object
        session: Database session
        state: FSM context
        data: Handler data
    """
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await show_levels_management(message, session, **data)
        return

    try:
        new_max = int(message.text.strip())
        if new_max < 1 or new_max > 5:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Введите число от 1 до 5.",
            reply_markup=cancel_keyboard(),
        )
        return

    # Get admin info for logging
    admin_id = data.get("admin_id")
    from app.repositories.admin_repository import AdminRepository
    admin_repo = AdminRepository(session)
    admin = await admin_repo.get_by_id(admin_id) if admin_id else None
    admin_info = f"admin {admin.telegram_id}" if admin else "unknown admin"

    global_settings_repo = GlobalSettingsRepository(session)
    await global_settings_repo.update_settings(max_open_deposit_level=new_max)
    await session.commit()
    
    logger.info(f"Max open deposit level changed to {new_max} by {admin_info}")

    await message.answer(
        f"✅ Максимальный уровень успешно изменён на **{new_max}**.",
        parse_mode="Markdown",
    )
    
    await clear_state_preserve_admin_token(state)
    await show_levels_management(message, session, **data)


@router.message(AdminDepositManagementStates.managing_level)
async def process_level_action(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Process level management action.
    
    Args:
        message: Message object
        session: Database session
        state: FSM context
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return
    
    # Check for back button
    if message.text in ["◀️ Назад", "◀️ Назад к уровням"]:
        await clear_state_preserve_admin_token(state)
        await show_levels_management(message, session, **data)
        return
    
    # Check for ROI corridor management button
    if message.text == "💰 Настроить коридор доходности":
        # Redirect to ROI corridor handler
        from bot.handlers.admin.roi_corridor import show_level_roi_config
        state_data = await state.get_data()
        level = state_data.get("managing_level")
        if level:
            await clear_state_preserve_admin_token(state)
            await show_level_roi_config(message, session, state, level, from_level_management=True, **data)
        return
    
    # Get level from state
    state_data = await state.get_data()
    level = state_data.get("managing_level")

    if not level:
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "❌ Ошибка: уровень не найден.",
            reply_markup=admin_deposit_management_keyboard(),
        )
        return

    version_repo = DepositLevelVersionRepository(session)
    current_version = await version_repo.get_current_version(level)

    if not current_version:
        await clear_state_preserve_admin_token(state)
        await message.answer(
            f"❌ Уровень {level} не найден.",
            reply_markup=admin_deposit_management_keyboard(),
        )
        return

    # Process action with explicit confirmation
    if message.text in ("✅ Включить уровень", "❌ Отключить уровень"):
        target_status = (
            "enable" if message.text == "✅ Включить уровень" else "disable"
        )
        status_text = "ВКЛЮЧИТЬ" if target_status == "enable" else "ОТКЛЮЧИТЬ"

        await state.update_data(
            level_action=target_status,
            level_current_active=current_version.is_active,
        )
        await state.set_state(
            AdminDepositManagementStates.confirming_level_status
        )

        await message.answer(
            "⚠️ Подтверждение\n\n"
            f"Вы хотите {status_text} уровень {level}?\n\n"
            "❗️ ВАЖНО:\n"
            "• При включении пользователи смогут создавать новые депозиты "
            "этого уровня\n"
            "• При отключении новые депозиты этого уровня создавать нельзя, "
            "но существующие продолжат работать\n\n"
            "Подтвердите действие (Да/Нет).",
            reply_markup=cancel_keyboard(),
        )
        return

    await message.answer(
        "❌ Неизвестное действие.",
        reply_markup=admin_deposit_level_actions_keyboard(
            level, current_version.is_active
        ),
    )


@router.message(AdminDepositManagementStates.confirming_level_status)
async def confirm_level_status_change(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Confirm enabling/disabling a deposit level.

    Args:
        message: Message object
        session: Database session
        state: FSM context
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    # Handle cancellation
    if message.text in ("❌ Отмена", "◀️ Назад", "◀️ Назад к уровням"):
        await clear_state_preserve_admin_token(state)
        await show_levels_management(message, session, **data)
        return

    normalized = (message.text or "").strip().lower()
    if normalized not in ("да", "yes", "✅ да"):
        # Treat anything other than explicit "yes" as cancellation
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "❌ Действие отменено.",
            reply_markup=admin_deposit_levels_keyboard(),
        )
        return

    state_data = await state.get_data()
    level = state_data.get("managing_level")
    action = state_data.get("level_action")

    if not level or action not in ("enable", "disable"):
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "❌ Ошибка: данные уровня не найдены.",
            reply_markup=admin_deposit_management_keyboard(),
        )
        return

    version_repo = DepositLevelVersionRepository(session)
    current_version = await version_repo.get_current_version(level)

    if not current_version:
        await clear_state_preserve_admin_token(state)
        await message.answer(
            f"❌ Уровень {level} не найден.",
            reply_markup=admin_deposit_management_keyboard(),
        )
        return

    # Apply status change
    if action == "enable":
        current_version.is_active = True
        status_msg = "✅ Уровень {level} включён!"
        notify_action = "включён"
    else:
        current_version.is_active = False
        status_msg = "❌ Уровень {level} отключён!"
        notify_action = "отключён"

    await session.commit()

    await message.answer(
        status_msg.format(level=level),
        reply_markup=admin_deposit_levels_keyboard(),
    )

    # Notify other admins about level status change
    try:
        from app.repositories.admin_repository import AdminRepository
        from bot.utils.notification import send_telegram_message

        admin_id = data.get("admin_id")
        admin_repo = AdminRepository(session)
        all_admins = await admin_repo.get_extended_admins()

        notification_text = (
            "🔔 **Изменён статус уровня депозитов**\n\n"
            f"**Уровень:** {level}\n"
            f"**Статус:** {notify_action}\n"
        )
        if admin_id:
            notification_text += f"**Изменил:** Admin ID {admin_id}"

        for admin in all_admins:
            if admin_id and admin.id == admin_id:
                continue
            try:
                await send_telegram_message(admin.telegram_id, notification_text)
            except Exception as e:
                logger.error(
                    "Failed to notify admin about level status change",
                    extra={"admin_id": admin.id, "error": str(e)},
                )
    except Exception as e:
        logger.error(
            "Failed to notify admins about level status change",
            extra={"error": str(e)},
        )

    await clear_state_preserve_admin_token(state)


@router.message(F.text == "📋 Pending депозиты")
async def show_pending_deposits(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Show all pending deposits.
    
    Args:
        message: Message object
        session: Database session
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    deposit_repo = DepositRepository(session)
    
    # Get pending deposits
    pending_deposits = await deposit_repo.find_by(
        status=TransactionStatus.PENDING.value
    )
    
    if not pending_deposits:
        await message.answer(
            "ℹ️ Нет pending депозитов.",
            reply_markup=admin_deposit_management_keyboard(),
        )
        return
    
    text = "📋 **Pending депозиты**\n\n"
    
    for deposit in pending_deposits[:10]:  # Limit to 10
        # Get user info
        user = deposit.user
        
        text += (
            f"🆔 Deposit ID: `{deposit.id}`\n"
            f"👤 User: {user.telegram_id} (@{user.username or 'N/A'})\n"
            f"📊 Уровень: {deposit.level}\n"
            f"💰 Сумма: {format_usdt(deposit.amount)}\n"
            f"📅 Дата: {deposit.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        )
        
        if deposit.tx_hash:
            text += f"🔗 TX: `{deposit.tx_hash[:16]}...`\n"
        
        text += "\n"
    
    if len(pending_deposits) > 10:
        text += f"\n... и ещё {len(pending_deposits) - 10} депозитов"
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_deposit_management_keyboard(),
    )


@router.message(F.text == "📈 ROI статистика")
async def show_roi_statistics(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Show ROI statistics for all levels.
    
    Args:
        message: Message object
        session: Database session
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    deposit_repo = DepositRepository(session)
    
    text = "📈 **ROI Статистика**\n\n"
    
    for level_num in range(1, 6):
        # Get active deposits for this level
        stmt = select(Deposit).where(
            Deposit.level == level_num,
            Deposit.status == TransactionStatus.CONFIRMED.value,
            Deposit.is_roi_completed == False,  # noqa: E712
        )
        
        result = await session.execute(stmt)
        active_deposits = result.scalars().all()
        
        if not active_deposits:
            continue
        
        # Calculate statistics
        total_deposits = len(active_deposits)
        total_paid = sum(d.roi_paid_amount for d in active_deposits)
        total_cap = sum(d.roi_cap_amount for d in active_deposits)
        avg_progress = (total_paid / total_cap * 100) if total_cap > 0 else 0
        
        # Find deposits close to completion (>80%)
        close_to_completion = [
            d for d in active_deposits
            if (d.roi_paid_amount / d.roi_cap_amount * 100) > 80
        ]
        
        emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"][level_num - 1]
        text += f"{emoji} **Уровень {level_num}:**\n"
        text += f"   Активных: {total_deposits}\n"
        text += f"   Выплачено: {format_usdt(total_paid)}\n"
        text += f"   Средний прогресс: {avg_progress:.1f}%\n"
        
        if close_to_completion:
            text += f"   🔥 Близки к завершению: {len(close_to_completion)}\n"
        
        text += "\n"
    
    if text == "📈 **ROI Статистика**\n\n":
        text += "ℹ️ Нет активных депозитов с незавершённым ROI."
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_deposit_management_keyboard(),
    )


@router.message(F.text == "◀️ Назад в админ-панель")
@router.message(F.text == "👑 Админ-панель")
async def back_to_admin_panel(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Return to admin panel.
    
    Args:
        message: Message object
        session: Database session
        state: FSM context
        data: Handler data
    """
    await clear_state_preserve_admin_token(state)
    from bot.handlers.admin.panel import handle_admin_panel_button
    
    await handle_admin_panel_button(message, session, **data)
