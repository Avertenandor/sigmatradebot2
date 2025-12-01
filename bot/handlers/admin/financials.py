"""
Financial Report Handler.

Implements the admin interface for viewing financial reports and user statistics.
Uses Reply Keyboards for navigation.
"""

import math
from typing import Any

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.financial_report_service import (
    FinancialReportService,
    UserFinancialDTO,
    UserDetailedFinancialDTO,
)
from bot.keyboards.reply import (
    admin_financial_list_keyboard,
    admin_keyboard,
    admin_user_financial_keyboard,
    admin_back_keyboard,
    admin_user_financial_detail_keyboard,
    admin_deposits_list_keyboard,
    admin_withdrawals_list_keyboard,
    admin_wallet_history_keyboard,
    get_admin_keyboard_from_data,
)
from bot.utils.formatters import escape_md, format_tx_hash_with_link
from bot.utils.menu_buttons import is_menu_button
from bot.utils.admin_utils import clear_state_preserve_admin_token

router = Router()


class AdminFinancialStates(StatesGroup):
    """States for financial reporting section."""
    viewing_list = State()
    viewing_user = State()
    viewing_withdrawals = State()
    viewing_user_detail = State()  # Детальная карточка пользователя
    viewing_deposits_list = State()  # Полный список депозитов
    viewing_withdrawals_list = State()  # Полный список выводов
    viewing_wallet_history = State()  # История смены кошельков


@router.message(StateFilter('*'), F.text.contains("Финансовая"))
async def show_financial_list(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Show paginated list of users with financial summary.
    Entry point for the section.
    """
    await clear_state_preserve_admin_token(state)
    logger.info(f"[FINANCIALS] Handler triggered by: {message.text}")
    # Проверка прав доступа: любой админ
    # R-NEW: Allow basic admins to view financial reports (per user request)
    # Previously restricted to extended/super, now open.
    pass

    service = FinancialReportService(session)
    
    # Default page 1
    page = 1
    per_page = 10
    
    users, total_count = await service.get_users_financial_summary(page, per_page)
    total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1

    await state.set_state(AdminFinancialStates.viewing_list)
    await state.update_data(current_page=page, total_pages=total_pages)

    text = (
        "💰 **Финансовая отчетность**\n\n"
        f"Всего пользователей: `{total_count}`\n"
        "Выберите пользователя для просмотра детальной информации:\n\n"
        "Формат: `User | Ввод | Вывод`"
    )

    await message.answer(
        text,
        parse_mode="MarkdownV2",
        reply_markup=admin_financial_list_keyboard(users, page, total_pages),
    )


@router.message(AdminFinancialStates.viewing_list, F.text.in_({"⬅ Предыдущая", "Следующая ➡"}))
async def handle_pagination(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle pagination for financial list."""
    state_data = await state.get_data()
    current_page = state_data.get("current_page", 1)
    total_pages = state_data.get("total_pages", 1)

    if message.text == "⬅ Предыдущая" and current_page > 1:
        current_page -= 1
    elif message.text == "Следующая ➡" and current_page < total_pages:
        current_page += 1
    else:
        # No change needed
        return

    service = FinancialReportService(session)
    users, total_count = await service.get_users_financial_summary(current_page, 10)
    
    # Re-calculate in case count changed
    total_pages = math.ceil(total_count / 10) if total_count > 0 else 1
    if current_page > total_pages:
        current_page = total_pages

    await state.update_data(current_page=current_page, total_pages=total_pages)
    
    text = (
        "💰 **Финансовая отчетность**\n\n"
        f"Всего пользователей: `{total_count}`\n"
        f"Страница: `{current_page}/{total_pages}`\n"
        "Выберите пользователя для просмотра детальной информации:"
    )

    await message.answer(
        text,
        parse_mode="MarkdownV2",
        reply_markup=admin_financial_list_keyboard(users, current_page, total_pages),
    )


@router.message(AdminFinancialStates.viewing_list, F.text.regexp(r'^👤 \d+\. @?'))
async def handle_user_selection(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle selection of a user from the list."""
    # Format is "👤 {id}. {username} | ..."
    try:
        # Extract ID from start of string
        user_id_str = message.text.split('.')[0].replace('👤 ', '')
        user_id = int(user_id_str)
    except (ValueError, IndexError):
        await message.answer("❌ Ошибка при выборе пользователя.")
        return

    service = FinancialReportService(session)
    details = await service.get_user_financial_details(user_id)

    if not details:
        await message.answer("❌ Пользователь не найден.")
        return

    # Escape data for MarkdownV2
    username = escape_md(details.user.username or "Нет юзернейма")
    full_name = escape_md(f"{details.user.telegram_id}") # Use ID if name not available easily here
    
    reg_date = details.user.created_at.strftime('%d\\.%m\\.%Y')
    last_active = details.user.last_active.strftime('%d\\.%m\\.%Y %H:%M') if details.user.last_active else "Неизвестно"
    
    last_dep = details.last_deposit_date.strftime('%d\\.%m\\.%Y %H:%M') if details.last_deposit_date else "Нет"
    last_with = details.last_withdrawal_date.strftime('%d\\.%m\\.%Y %H:%M') if details.last_withdrawal_date else "Нет"

    text = (
        f"📂 **Личное дело пользователя**\n"
        f"ID: `{details.user.id}`\n"
        f"Telegram ID: `{details.user.telegram_id}`\n"
        f"Username: @{username}\n\n"
        
        f"📅 Регистрация: {reg_date}\n"
        f"🕒 Активность: {last_active}\n\n"
        
        f"💰 **Финансы**:\n"
        f"📥 Всего внесено: `{details.total_deposited:.2f}` USDT\n"
        f"📤 Всего выведено: `{details.total_withdrawn:.2f}` USDT\n"
        f"📈 Начислено ROI: `{details.total_earned:.2f}` USDT\n"
        f"📊 Активных депозитов: `{details.active_deposits_count}`\n\n"
        
        f"Последний депозит: {last_dep}\n"
        f"Последний вывод: {last_with}"
    )

    await state.set_state(AdminFinancialStates.viewing_user)
    await state.update_data(selected_user_id=user_id)

    await message.answer(
        text,
        parse_mode="MarkdownV2",
        reply_markup=admin_user_financial_keyboard(),
    )


@router.message(AdminFinancialStates.viewing_user, F.text == "💸 История выводов")
async def show_user_withdrawals(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show recent withdrawals with copyable hashes."""
    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: ID пользователя потерян.")
        return

    service = FinancialReportService(session)
    withdrawals = await service.get_user_withdrawals(user_id, limit=10)

    if not withdrawals:
        await message.answer("💸 У пользователя нет подтвержденных выводов.")
        return

    text = "💸 **История выводов (последние 10):**\n\n"
    
    for tx in withdrawals:
        date_str = tx.created_at.strftime('%d\\.%m\\.%Y %H:%M')
        amount = f"{tx.amount:.2f}"
        tx_hash = escape_md(tx.tx_hash) if tx.tx_hash else "Нет хеша"
        
        text += (
            f"📅 {date_str}\n"
            f"💵 `{amount}` USDT\n"
            f"🔗 Hash: `{tx_hash}`\n"
            f"──────────────────\n"
        )

    await state.set_state(AdminFinancialStates.viewing_withdrawals)
    # Use simple back keyboard for this leaf view
    await message.answer(
        text,
        parse_mode="MarkdownV2",
        reply_markup=admin_back_keyboard(),
    )


@router.message(AdminFinancialStates.viewing_user, F.text == "📜 История начислений")
async def show_user_accruals_stub(
    message: Message,
    state: FSMContext,
) -> None:
    """Stub for accrual history (can be expanded later)."""
    # For now, just show a message, as detailed accrual logs might be huge
    # Could reuse the Transaction model if we log accruals there, but currently
    # they are in DepositReward which is separate.
    await message.answer("ℹ️ Детальный лог начислений доступен в базе данных. (Функция в разработке)")


@router.message(
    StateFilter(AdminFinancialStates.viewing_user, AdminFinancialStates.viewing_withdrawals),
    F.text.in_({"◀️ Назад", "◀️ Назад к списку"})
)
async def handle_back(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle back navigation."""
    current_state = await state.get_state()
    
    if current_state == AdminFinancialStates.viewing_withdrawals:
        # Back to User Profile
        state_data = await state.get_data()
        user_id = state_data.get("selected_user_id")
        if user_id:
            # Re-render user profile
            # Hack: create a fake message object to reuse handle_user_selection logic? 
            # Or better, extract rendering logic.
            # For simplicity, let's call the service again and show profile.
            service = FinancialReportService(session)
            details = await service.get_user_financial_details(user_id)
            if details:
                # (Reuse text generation logic from handle_user_selection - simplified here)
                username = escape_md(details.user.username or "Нет юзернейма")
                text = (
                    f"📂 **Личное дело пользователя**\n"
                    f"ID: `{details.user.id}`\n"
                    f"Username: @{username}\n"
                    "Выберите действие:"
                )
                await state.set_state(AdminFinancialStates.viewing_user)
                await message.answer(text, parse_mode="MarkdownV2", reply_markup=admin_user_financial_keyboard())
                return

    # Default: Back to List
    await show_financial_list(message, session, state, **data)


@router.message(AdminFinancialStates.viewing_list, F.text.startswith("👤"))
async def show_user_financial_detail(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show detailed financial card for selected user."""
    # Проверка прав доступа
    is_super_admin = data.get("is_super_admin", False)
    is_extended_admin = data.get("is_extended_admin", False)
    
    if not (is_super_admin or is_extended_admin):
        await message.answer("❌ Доступ запрещён.")
        return
    
    # Парсим ID пользователя из текста кнопки: "👤 123. username | +100 | -50"
    try:
        text_parts = message.text.split(".")
        user_id = int(text_parts[0].replace("👤", "").strip())
    except (ValueError, IndexError):
        await message.answer("❌ Ошибка при разборе ID пользователя")
        return
    
    service = FinancialReportService(session)
    dto = await service.get_user_detailed_financial_report(user_id)
    
    if not dto:
        await message.answer("❌ Пользователь не найден")
        return
    
    # Сохраняем ID для навигации
    await state.update_data(selected_user_id=user_id)
    await state.set_state(AdminFinancialStates.viewing_user_detail)
    
    # Форматируем детальную карточку
    text = _format_user_financial_detail(dto)
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_user_financial_detail_keyboard(),
        disable_web_page_preview=True
    )


def _format_user_financial_detail(dto: UserDetailedFinancialDTO) -> str:
    """Format detailed user financial card."""
    username = f"@{dto.username}" if dto.username else f"ID: {dto.telegram_id}"
    
    # Общая информация
    text = (
        f"📂 **Детальная финансовая карточка**\n\n"
        f"👤 Пользователь: {username}\n"
        f"🆔 User ID: `{dto.user_id}`\n"
        f"💳 Кошелек: `{dto.current_wallet[:10]}...{dto.current_wallet[-8:]}`\n\n"
        f"💰 **Финансовая сводка:**\n"
        f"├ Депозиты: `{float(dto.total_deposited):.2f}` USDT\n"
        f"├ Заработано: `{float(dto.total_earned):.2f}` USDT\n"
        f"├ Выведено: `{float(dto.total_withdrawn):.2f}` USDT\n"
        f"├ Баланс: `{float(dto.balance):.2f}` USDT\n"
        f"└ Ожидает: `{float(dto.pending_earnings):.2f}` USDT\n\n"
    )
    
    # Последние 5 депозитов
    if dto.deposits:
        text += "📊 **Последние депозиты** (топ-5):\n"
        for i, dep in enumerate(dto.deposits[:5], 1):
            status_emoji = "✅" if dep.is_completed else "⏳"
            tx_link = format_tx_hash_with_link(dep.tx_hash) if dep.tx_hash else "—"
            text += (
                f"{i}. {status_emoji} Lvl {dep.level}: `{float(dep.amount):.2f}` USDT\n"
                f"   ROI: `{float(dep.roi_paid):.2f}`/`{float(dep.roi_cap):.2f}` | TX: {tx_link}\n"
            )
        text += f"\n_Всего депозитов: {len(dto.deposits)}_\n\n"
    else:
        text += "📊 Депозитов нет\n\n"
    
    # Последние 5 выводов
    if dto.withdrawals:
        text += "💸 **Последние выводы** (топ-5):\n"
        for i, wd in enumerate(dto.withdrawals[:5], 1):
            status_emoji = "✅" if wd.status == "confirmed" else "⏳"
            tx_link = format_tx_hash_with_link(wd.tx_hash) if wd.tx_hash else "—"
            text += (
                f"{i}. {status_emoji} `{float(wd.amount):.2f}` USDT\n"
                f"   TX: {tx_link}\n"
            )
        text += f"\n_Всего выводов: {len(dto.withdrawals)}_\n\n"
    else:
        text += "💸 Выводов нет\n\n"
    
    # История смены кошельков
    if dto.wallet_history:
        text += f"💳 **История кошельков:** {len(dto.wallet_history)} изменений\n\n"
    else:
        text += "💳 Кошелек не менялся\n\n"
    
    text += "Выберите раздел для детального просмотра:"
    
    return text


@router.message(AdminFinancialStates.viewing_user_detail, F.text == "📊 Все депозиты")
async def show_all_deposits(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show full list of user deposits with pagination."""
    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не выбран")
        return
    
    service = FinancialReportService(session)
    dto = await service.get_user_detailed_financial_report(user_id)
    
    if not dto or not dto.deposits:
        await message.answer("📊 У пользователя нет депозитов")
        return
    
    # Пагинация: 10 депозитов на страницу
    page = 1
    per_page = 10
    total_pages = math.ceil(len(dto.deposits) / per_page)
    
    await state.update_data(deposits_page=page, total_deposits_pages=total_pages)
    await state.set_state(AdminFinancialStates.viewing_deposits_list)
    
    text = _format_deposits_page(dto.deposits, page, per_page, total_pages)
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_deposits_list_keyboard(page, total_pages),
        disable_web_page_preview=True
    )


def _format_deposits_page(
    deposits: list, page: int, per_page: int, total_pages: int
) -> str:
    """Format deposits page."""
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_deposits = deposits[start_idx:end_idx]
    
    text = f"📊 **Все депозиты** (стр. {page}/{total_pages}):\n\n"
    
    for i, dep in enumerate(page_deposits, start=start_idx + 1):
        status_emoji = "✅" if dep.is_completed else "⏳"
        tx_link = format_tx_hash_with_link(dep.tx_hash) if dep.tx_hash else "—"
        date_str = dep.created_at.strftime("%Y-%m-%d %H:%M")
        
        text += (
            f"{i}. {status_emoji} **Lvl {dep.level}** | `{float(dep.amount):.2f}` USDT\n"
            f"   Дата: {date_str}\n"
            f"   ROI: `{float(dep.roi_paid):.2f}`/`{float(dep.roi_cap):.2f}` USDT"
        )
        
        if dep.roi_percent:
            text += f" ({float(dep.roi_percent):.1f}%)\n"
        else:
            text += "\n"
        
        text += f"   TX: {tx_link}\n\n"
    
    return text


@router.message(AdminFinancialStates.viewing_user_detail, F.text == "💸 Все выводы")
async def show_all_withdrawals(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show full list of user withdrawals with pagination."""
    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не выбран")
        return
    
    service = FinancialReportService(session)
    dto = await service.get_user_detailed_financial_report(user_id)
    
    if not dto or not dto.withdrawals:
        await message.answer("💸 У пользователя нет выводов")
        return
    
    # Пагинация: 10 выводов на страницу
    page = 1
    per_page = 10
    total_pages = math.ceil(len(dto.withdrawals) / per_page)
    
    await state.update_data(withdrawals_page=page, total_withdrawals_pages=total_pages)
    await state.set_state(AdminFinancialStates.viewing_withdrawals_list)
    
    text = _format_withdrawals_page(dto.withdrawals, page, per_page, total_pages)
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_withdrawals_list_keyboard(page, total_pages),
        disable_web_page_preview=True
    )


def _format_withdrawals_page(
    withdrawals: list, page: int, per_page: int, total_pages: int
) -> str:
    """Format withdrawals page."""
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_withdrawals = withdrawals[start_idx:end_idx]
    
    text = f"💸 **Все выводы** (стр. {page}/{total_pages}):\n\n"
    
    for i, wd in enumerate(page_withdrawals, start=start_idx + 1):
        status_emoji = "✅" if wd.status == "confirmed" else "⏳"
        tx_link = format_tx_hash_with_link(wd.tx_hash) if wd.tx_hash else "—"
        date_str = wd.created_at.strftime("%Y-%m-%d %H:%M")
        
        text += (
            f"{i}. {status_emoji} `{float(wd.amount):.2f}` USDT\n"
            f"   Дата: {date_str}\n"
            f"   Статус: {wd.status}\n"
            f"   TX: {tx_link}\n\n"
        )
    
    return text


@router.message(AdminFinancialStates.viewing_user_detail, F.text == "💳 История кошельков")
async def show_wallet_history(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show wallet change history."""
    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не выбран")
        return
    
    service = FinancialReportService(session)
    dto = await service.get_user_detailed_financial_report(user_id)
    
    if not dto or not dto.wallet_history:
        await message.answer("💳 Пользователь не менял кошелек")
        return
    
    await state.set_state(AdminFinancialStates.viewing_wallet_history)
    
    text = "💳 **История смены кошельков:**\n\n"
    
    for i, wh in enumerate(dto.wallet_history, 1):
        date_str = wh.changed_at.strftime("%Y-%m-%d %H:%M")
        old_short = f"{wh.old_wallet[:10]}...{wh.old_wallet[-8:]}"
        new_short = f"{wh.new_wallet[:10]}...{wh.new_wallet[-8:]}"
        
        text += (
            f"{i}. **{date_str}**\n"
            f"   Старый: `{old_short}`\n"
            f"   Новый: `{new_short}`\n\n"
        )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_wallet_history_keyboard()
    )


@router.message(
    AdminFinancialStates.viewing_user_detail,
    F.text == "⬅ Назад к списку"
)
async def back_to_list_from_detail(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Return to users list from detail card."""
    await show_financial_list(message, session, state, **data)


@router.message(
    AdminFinancialStates.viewing_deposits_list,
    F.text.in_({"⬅ Предыдущая", "Следующая ➡"})
)
async def handle_deposits_pagination(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle pagination for deposits list."""
    state_data = await state.get_data()
    current_page = state_data.get("deposits_page", 1)
    total_pages = state_data.get("total_deposits_pages", 1)
    user_id = state_data.get("selected_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка")
        return
    
    # Update page
    if message.text == "⬅ Предыдущая" and current_page > 1:
        current_page -= 1
    elif message.text == "Следующая ➡" and current_page < total_pages:
        current_page += 1
    else:
        return
    
    await state.update_data(deposits_page=current_page)
    
    # Get deposits
    service = FinancialReportService(session)
    dto = await service.get_user_detailed_financial_report(user_id)
    
    if not dto or not dto.deposits:
        await message.answer("❌ Ошибка загрузки данных")
        return
    
    per_page = 10
    text = _format_deposits_page(dto.deposits, current_page, per_page, total_pages)
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_deposits_list_keyboard(current_page, total_pages),
        disable_web_page_preview=True
    )


@router.message(
    AdminFinancialStates.viewing_deposits_list,
    F.text == "◀️ К карточке"
)
async def back_to_card_from_deposits(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Return to user card from deposits list."""
    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка")
        return
    
    service = FinancialReportService(session)
    dto = await service.get_user_detailed_financial_report(user_id)
    
    if not dto:
        await message.answer("❌ Пользователь не найден")
        return
    
    await state.set_state(AdminFinancialStates.viewing_user_detail)
    text = _format_user_financial_detail(dto)
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_user_financial_detail_keyboard(),
        disable_web_page_preview=True
    )


@router.message(
    AdminFinancialStates.viewing_withdrawals_list,
    F.text.in_({"⬅ Предыдущая", "Следующая ➡"})
)
async def handle_withdrawals_pagination(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle pagination for withdrawals list."""
    state_data = await state.get_data()
    current_page = state_data.get("withdrawals_page", 1)
    total_pages = state_data.get("total_withdrawals_pages", 1)
    user_id = state_data.get("selected_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка")
        return
    
    # Update page
    if message.text == "⬅ Предыдущая" and current_page > 1:
        current_page -= 1
    elif message.text == "Следующая ➡" and current_page < total_pages:
        current_page += 1
    else:
        return
    
    await state.update_data(withdrawals_page=current_page)
    
    # Get withdrawals
    service = FinancialReportService(session)
    dto = await service.get_user_detailed_financial_report(user_id)
    
    if not dto or not dto.withdrawals:
        await message.answer("❌ Ошибка загрузки данных")
        return
    
    per_page = 10
    text = _format_withdrawals_page(dto.withdrawals, current_page, per_page, total_pages)
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_withdrawals_list_keyboard(current_page, total_pages),
        disable_web_page_preview=True
    )


@router.message(
    AdminFinancialStates.viewing_withdrawals_list,
    F.text == "◀️ К карточке"
)
async def back_to_card_from_withdrawals(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Return to user card from withdrawals list."""
    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка")
        return
    
    service = FinancialReportService(session)
    dto = await service.get_user_detailed_financial_report(user_id)
    
    if not dto:
        await message.answer("❌ Пользователь не найден")
        return
    
    await state.set_state(AdminFinancialStates.viewing_user_detail)
    text = _format_user_financial_detail(dto)
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_user_financial_detail_keyboard(),
        disable_web_page_preview=True
    )


@router.message(
    AdminFinancialStates.viewing_wallet_history,
    F.text == "◀️ К карточке"
)
async def back_to_card_from_wallet_history(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Return to user card from wallet history."""
    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка")
        return
    
    service = FinancialReportService(session)
    dto = await service.get_user_detailed_financial_report(user_id)
    
    if not dto:
        await message.answer("❌ Пользователь не найден")
        return
    
    await state.set_state(AdminFinancialStates.viewing_user_detail)
    text = _format_user_financial_detail(dto)
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_user_financial_detail_keyboard(),
        disable_web_page_preview=True
    )


@router.message(StateFilter(AdminFinancialStates), F.text == "👑 Админ-панель")
async def back_to_admin_panel(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Return to main admin panel from any financials state."""
    # Сохраняем admin_session_token и возвращаемся в общий хендлер панели
    await clear_state_preserve_admin_token(state)
    from bot.handlers.admin.panel import handle_admin_panel_button

    await handle_admin_panel_button(message, session, **data)

