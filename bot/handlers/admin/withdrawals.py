"""
Admin Withdrawals Handler
Handles withdrawal approval and rejection
"""

import re
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.models.transaction import Transaction
from app.models.enums import TransactionStatus, TransactionType
from app.services.admin_log_service import AdminLogService
from app.services.blockchain_service import get_blockchain_service
from app.services.notification_service import NotificationService
from app.services.user_service import UserService
from app.services.withdrawal_service import WithdrawalService
from bot.keyboards.reply import (
    admin_withdrawals_keyboard,
    admin_keyboard,
    withdrawal_list_keyboard,
    withdrawal_confirm_keyboard,
    admin_withdrawal_detail_keyboard,
)
from bot.states.admin_states import AdminStates
from bot.utils.formatters import format_usdt
from bot.utils.admin_utils import clear_state_preserve_admin_token

WITHDRAWALS_PER_PAGE = 8

router = Router(name="admin_withdrawals")


@router.message(F.text == "⏳ Ожидающие выводы")
async def handle_pending_withdrawals(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show list of pending withdrawals as buttons for selection."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    withdrawal_service = WithdrawalService(session)
    pending = await withdrawal_service.get_pending_withdrawals()

    if not pending:
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "📭 Нет ожидающих заявок на вывод.",
            reply_markup=admin_withdrawals_keyboard(),
        )
        return

    # Pagination
    page = 1
    total = len(pending)
    total_pages = (total + WITHDRAWALS_PER_PAGE - 1) // WITHDRAWALS_PER_PAGE
    
    start_idx = (page - 1) * WITHDRAWALS_PER_PAGE
    end_idx = start_idx + WITHDRAWALS_PER_PAGE
    page_withdrawals = pending[start_idx:end_idx]

    await state.set_state(AdminStates.selecting_withdrawal)
    await state.update_data(page=page)

    text = (
        f"⏳ **Ожидающие заявки на вывод**\n\n"
        f"📋 Всего заявок: {total}\n"
        f"📄 Страница: {page}/{total_pages}\n\n"
        "Нажмите на заявку для просмотра деталей:"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=withdrawal_list_keyboard(
            page_withdrawals, page, total_pages
        ),
    )


@router.message(F.text == "◀️ Назад к выводам")
@router.message(F.text == "❌ Нет, отменить", AdminStates.confirming_withdrawal_action)
async def handle_cancel_withdrawal_action(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Cancel withdrawal action and return to list."""
    # Re-use logic to show list
    await handle_pending_withdrawals(message, session, state, **data)


@router.message(F.text == "⬅️ Пред.", AdminStates.selecting_withdrawal)
async def handle_prev_page(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Go to previous page of withdrawals."""
    fsm_data = await state.get_data()
    page = fsm_data.get("page", 1) - 1
    
    # We need to refresh the list to handle pagination properly
    withdrawal_service = WithdrawalService(session)
    pending = await withdrawal_service.get_pending_withdrawals()
    
    if not pending:
        await message.answer("📭 Заявок больше нет.")
        await handle_pending_withdrawals(message, session, state, **data)
        return

    total = len(pending)
    total_pages = (total + WITHDRAWALS_PER_PAGE - 1) // WITHDRAWALS_PER_PAGE
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * WITHDRAWALS_PER_PAGE
    end_idx = start_idx + WITHDRAWALS_PER_PAGE
    page_withdrawals = pending[start_idx:end_idx]
    
    await state.update_data(page=page)
    
    text = (
        f"⏳ **Ожидающие заявки на вывод**\n\n"
        f"📋 Всего заявок: {total}\n"
        f"📄 Страница: {page}/{total_pages}\n\n"
        "Нажмите на заявку для просмотра деталей:"
    )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=withdrawal_list_keyboard(
            page_withdrawals, page, total_pages
        ),
    )


@router.message(F.text == "След. ➡️", AdminStates.selecting_withdrawal)
async def handle_next_page(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Go to next page of withdrawals."""
    fsm_data = await state.get_data()
    page = fsm_data.get("page", 1) + 1
    
    # Reuse logic (duplicate code reduction would be better but keeping it simple for now)
    withdrawal_service = WithdrawalService(session)
    pending = await withdrawal_service.get_pending_withdrawals()
    
    if not pending:
        await message.answer("📭 Заявок больше нет.")
        await handle_pending_withdrawals(message, session, state, **data)
        return

    total = len(pending)
    total_pages = (total + WITHDRAWALS_PER_PAGE - 1) // WITHDRAWALS_PER_PAGE
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * WITHDRAWALS_PER_PAGE
    end_idx = start_idx + WITHDRAWALS_PER_PAGE
    page_withdrawals = pending[start_idx:end_idx]
    
    await state.update_data(page=page)
    
    text = (
        f"⏳ **Ожидающие заявки на вывод**\n\n"
        f"📋 Всего заявок: {total}\n"
        f"📄 Страница: {page}/{total_pages}\n\n"
        "Нажмите на заявку для просмотра деталей:"
    )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=withdrawal_list_keyboard(
            page_withdrawals, page, total_pages
        ),
    )


@router.message(
    F.text.regexp(r"^💸 #(\d+) \|"),
    AdminStates.selecting_withdrawal,
)
async def handle_withdrawal_selection(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Process withdrawal selection from button and show details."""
    text = message.text or ""

    # Extract withdrawal ID from button text: "💸 #123 | 100.00 | @user"
    match = re.match(r"^💸 #(\d+) \|", text)
    if not match:
        await message.answer(
            "❌ Не удалось определить заявку. Попробуйте снова.",
            reply_markup=admin_withdrawals_keyboard(),
        )
        await clear_state_preserve_admin_token(state)
        return

    withdrawal_id = int(match.group(1))

    # Get withdrawal details
    withdrawal_service = WithdrawalService(session)
    withdrawal = await withdrawal_service.get_withdrawal_by_id(withdrawal_id)

    if not withdrawal:
        await message.answer(
            f"❌ Заявка #{withdrawal_id} не найдена.",
            reply_markup=admin_withdrawals_keyboard(),
        )
        await clear_state_preserve_admin_token(state)
        return

    if withdrawal.status != TransactionStatus.PENDING.value:
        status_text = {
            TransactionStatus.CONFIRMED.value: "уже одобрена",
            TransactionStatus.FAILED.value: "уже отклонена",
        }.get(withdrawal.status, f"в статусе {withdrawal.status}")

        await message.answer(
            f"❌ Заявка #{withdrawal_id} {status_text}.",
            reply_markup=admin_withdrawals_keyboard(),
        )
        await clear_state_preserve_admin_token(state)
        return

    await state.update_data(withdrawal_id=withdrawal_id)
    await state.set_state(AdminStates.viewing_withdrawal)

    # Get user info and stats
    user_service = UserService(session)
    user = await user_service.find_by_id(withdrawal.user_id)
    username = f"@{user.username}" if user and user.username else f"ID: {withdrawal.user_id}"
    
    user_balance = await user_service.get_user_balance(withdrawal.user_id)
    history_text = ""
    if user_balance:
        total_dep = user_balance.get('total_deposits', 0)
        total_wd = user_balance.get('total_withdrawals', 0)
        history_text = f"📊 История: депозиты {format_usdt(total_dep)}, выводы {format_usdt(total_wd)}\n"

    date = withdrawal.created_at.strftime("%d.%m.%Y %H:%M")

    text = (
        f"💸 **Заявка на вывод #{withdrawal.id}**\n\n"
        f"👤 Пользователь: {username}\n"
        f"{history_text}"
        f"💰 Сумма: `{format_usdt(withdrawal.amount)} USDT`\n"
        f"💳 Кошелек: `{withdrawal.to_address}`\n"
        f"📅 Дата: {date}\n\n"
        "Выберите действие:"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_withdrawal_detail_keyboard(),
    )


@router.message(AdminStates.viewing_withdrawal, F.text == "✅ Одобрить")
async def handle_approve_request(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle approval request from detail view."""
    await state.update_data(withdrawal_action="approve")
    await _show_confirmation(message, state, session, "approve")


@router.message(AdminStates.viewing_withdrawal, F.text == "❌ Отклонить")
async def handle_reject_request(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle rejection request from detail view."""
    await state.update_data(withdrawal_action="reject")
    await _show_confirmation(message, state, session, "reject")


@router.message(AdminStates.viewing_withdrawal, F.text == "◀️ Назад к списку")
async def handle_back_to_list(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Return to withdrawal list."""
    await handle_pending_withdrawals(message, session, state, **data)


async def _show_confirmation(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    action: str,
) -> None:
    """Show confirmation dialog."""
    fsm_data = await state.get_data()
    withdrawal_id = fsm_data.get("withdrawal_id")
    
    if not withdrawal_id:
        await message.answer("❌ Ошибка: ID заявки не найден.")
        await handle_pending_withdrawals(message, session, state)
        return

    action_text = "ОДОБРИТЬ" if action == "approve" else "ОТКЛОНИТЬ"
    action_emoji = "✅" if action == "approve" else "❌"
    
    await state.set_state(AdminStates.confirming_withdrawal_action)
    
    await message.answer(
        f"{action_emoji} **Подтверждение: {action_text}**\n\n"
        f"📝 Заявка: #{withdrawal_id}\n\n"
        f"Вы уверены, что хотите **{action_text.lower()}** эту заявку?",
        parse_mode="Markdown",
        reply_markup=withdrawal_confirm_keyboard(withdrawal_id, action),
    )


@router.message(
    F.text.regexp(r"^✅ Да, (одобрить|отклонить) #(\d+)$"),
    AdminStates.confirming_withdrawal_action,
)
async def handle_confirm_withdrawal_action(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Execute the confirmed withdrawal action."""
    fsm_data = await state.get_data()
    action = fsm_data.get("withdrawal_action")
    withdrawal_id = fsm_data.get("withdrawal_id")

    await clear_state_preserve_admin_token(state)

    if not withdrawal_id:
        await message.answer(
            "❌ Ошибка: ID заявки не найден.",
            reply_markup=admin_withdrawals_keyboard(),
        )
        return

    withdrawal_service = WithdrawalService(session)
    user_service = UserService(session)
    notification_service = NotificationService(session)
    admin: Admin | None = data.get("admin")

    try:
        withdrawal = await withdrawal_service.get_withdrawal_by_id(withdrawal_id)

        if not withdrawal:
            await message.answer(
                f"❌ Заявка #{withdrawal_id} не найдена.",
                reply_markup=admin_withdrawals_keyboard(),
            )
            return

        if action == "approve":
            # Check maintenance mode
            from app.config.settings import settings

            if settings.blockchain_maintenance_mode:
                await message.answer(
                    "⚠️ **Blockchain в режиме обслуживания**\n\n"
                    "Операции с блокчейном временно недоступны.",
                    parse_mode="Markdown",
                    reply_markup=admin_withdrawals_keyboard(),
                )
                return

            # Check dual control
            withdrawal_amount = float(withdrawal.amount)
            requires_dual_control = (
                withdrawal_amount >= settings.dual_control_withdrawal_threshold
            )

            if requires_dual_control:
                # Create escrow for dual control
                from app.repositories.admin_action_escrow_repository import (
                    AdminActionEscrowRepository,
                )

                escrow_repo = AdminActionEscrowRepository(session)
                admin_id = admin.id if admin else None

                existing_escrow = await escrow_repo.get_pending_by_operation(
                    "WITHDRAWAL_APPROVAL", withdrawal_id
                )

                if existing_escrow:
                    if existing_escrow.initiator_admin_id == admin_id:
                        await message.answer(
                            f"⚠️ Для вывода {withdrawal_amount} USDT требуется "
                            "подтверждение второго администратора.\n\n"
                            f"Escrow #{existing_escrow.id} ожидает подтверждения.",
                            reply_markup=admin_withdrawals_keyboard(),
                        )
                        return

                escrow = await escrow_repo.create(
                    operation_type="WITHDRAWAL_APPROVAL",
                    target_id=withdrawal_id,
                    operation_data={
                        "transaction_id": withdrawal_id,
                        "amount": str(withdrawal.amount),
                        "user_id": withdrawal.user_id,
                        "to_address": withdrawal.to_address,
                    },
                    initiator_admin_id=admin_id,
                    expires_in_hours=settings.dual_control_escrow_expiry_hours,
                )
                await session.commit()

                await message.answer(
                    f"⚠️ Для вывода {withdrawal_amount} USDT требуется "
                    "подтверждение второго администратора.\n\n"
                    f"Escrow #{escrow.id} создан.",
                    reply_markup=admin_withdrawals_keyboard(),
                )
                return

            # Send blockchain transaction
            blockchain_service = get_blockchain_service()
            payment_result = await blockchain_service.send_payment(
                withdrawal.to_address, float(withdrawal.amount)
            )

            if not payment_result["success"]:
                error_msg = payment_result.get("error", "Неизвестная ошибка")
                await message.answer(
                    f"❌ Ошибка отправки: {error_msg}",
                    reply_markup=admin_withdrawals_keyboard(),
                )
                return

            tx_hash = payment_result["tx_hash"]
            admin_id = admin.id if admin else None
            success, error_msg = await withdrawal_service.approve_withdrawal(
                withdrawal_id, tx_hash, admin_id
            )

            if not success:
                await message.answer(
                    f"❌ Ошибка: {error_msg}",
                    reply_markup=admin_withdrawals_keyboard(),
                )
                return

            # Notify user
            user = await user_service.find_by_id(withdrawal.user_id)
            if user:
                logger.info(f"Attempting to notify user {user.id} (TG: {user.telegram_id}) about withdrawal {tx_hash}")
                notify_result = await notification_service.notify_withdrawal_processed(
                    user.telegram_id, float(withdrawal.amount), tx_hash
                )
                logger.info(f"Notification result for user {user.id}: {notify_result}")
            else:
                logger.warning(f"User {withdrawal.user_id} not found for notification")

            await message.answer(
                f"✅ **Заявка #{withdrawal_id} одобрена!**\n\n"
                f"💰 Сумма: {format_usdt(withdrawal.amount)} USDT\n"
                f"🔗 TX: `{tx_hash}`\n\n"
                "Средства отправлены пользователю.",
                parse_mode="Markdown",
                reply_markup=admin_withdrawals_keyboard(),
            )

            # Log action
            if admin:
                log_service = AdminLogService(session)
                await log_service.log_withdrawal_approved(
                    admin=admin,
                    withdrawal_id=withdrawal_id,
                    user_id=withdrawal.user_id,
                    amount=str(withdrawal.amount),
                )

        else:  # reject
            success, error_msg = await withdrawal_service.reject_withdrawal(
                withdrawal_id
            )

            if not success:
                await message.answer(
                    f"❌ Ошибка: {error_msg}",
                    reply_markup=admin_withdrawals_keyboard(),
                )
                return

            # Notify user
            user = await user_service.find_by_id(withdrawal.user_id)
            if user:
                await notification_service.notify_withdrawal_rejected(
                    user.telegram_id, float(withdrawal.amount)
                )

            await message.answer(
                f"❌ **Заявка #{withdrawal_id} отклонена**\n\n"
                f"💰 Сумма: {format_usdt(withdrawal.amount)} USDT\n\n"
                "Средства возвращены на баланс пользователя.",
                parse_mode="Markdown",
                reply_markup=admin_withdrawals_keyboard(),
            )

            # Log action
            if admin:
                log_service = AdminLogService(session)
                await log_service.log_withdrawal_rejected(
                    admin=admin,
                    withdrawal_id=withdrawal_id,
                    user_id=withdrawal.user_id,
                    reason=None,
                )

    except Exception as e:
        logger.error(f"Error processing withdrawal action: {e}")
        await message.answer(
            f"❌ Ошибка при обработке: {str(e)}",
            reply_markup=admin_withdrawals_keyboard(),
        )


@router.message(F.text == "📋 Одобренные выводы")
async def handle_approved_withdrawals(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show approved withdrawals"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    withdrawal_service = WithdrawalService(session)

    try:
        # Get approved withdrawals (last 10)
        stmt = (
            select(Transaction)
            .where(
                Transaction.type == TransactionType.WITHDRAWAL.value,
                Transaction.status == TransactionStatus.CONFIRMED.value,
            )
            .order_by(desc(Transaction.created_at))
            .limit(10)
        )
        result = await session.execute(stmt)
        approved_withdrawals = result.scalars().all()

        text = "✅ **Одобренные заявки на вывод**\n\n"

        if not approved_withdrawals:
            text += "Нет одобренных заявок."
        else:
            for idx, withdrawal in enumerate(approved_withdrawals, 1):
                date = withdrawal.created_at.strftime("%d.%m.%Y %H:%M")
                text += f"**{idx}. Заявка #{withdrawal.id}**\n"
                text += f"💰 Сумма: {format_usdt(withdrawal.amount)} USDT\n"
                text += f"👤 Пользователь ID: {withdrawal.user_id}\n"
                text += f"💳 Кошелек: `{withdrawal.to_address}`\n"
                if withdrawal.tx_hash:
                    text += f"🔗 TX: `{withdrawal.tx_hash}`\n"
                text += f"📅 Дата: {date}\n\n"

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=admin_withdrawals_keyboard(),
        )

    except Exception as e:
        await message.answer(
            f"❌ Ошибка при загрузке заявок: {str(e)}",
            reply_markup=admin_withdrawals_keyboard(),
        )


@router.message(F.text == "🚫 Отклоненные выводы")
async def handle_rejected_withdrawals(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show rejected withdrawals"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    withdrawal_service = WithdrawalService(session)

    try:
        # Get rejected withdrawals (last 10)
        stmt = (
            select(Transaction)
            .where(
                Transaction.type == TransactionType.WITHDRAWAL.value,
                Transaction.status == TransactionStatus.FAILED.value,
            )
            .order_by(desc(Transaction.created_at))
            .limit(10)
        )
        result = await session.execute(stmt)
        rejected_withdrawals = result.scalars().all()

        text = "❌ **Отклоненные заявки на вывод**\n\n"

        if not rejected_withdrawals:
            text += "Нет отклоненных заявок."
        else:
            for idx, withdrawal in enumerate(rejected_withdrawals, 1):
                date = withdrawal.created_at.strftime("%d.%m.%Y %H:%M")
                text += f"**{idx}. Заявка #{withdrawal.id}**\n"
                text += f"💰 Сумма: {format_usdt(withdrawal.amount)} USDT\n"
                text += f"👤 Пользователь ID: {withdrawal.user_id}\n"
                text += f"💳 Кошелек: `{withdrawal.to_address}`\n"
                text += f"📅 Дата: {date}\n\n"

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=admin_withdrawals_keyboard(),
        )

    except Exception as e:
        await message.answer(
            f"❌ Ошибка при загрузке заявок: {str(e)}",
            reply_markup=admin_withdrawals_keyboard(),
        )


@router.message(F.text == "👑 Админ-панель")
async def handle_back_to_admin_panel(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Return to admin panel from withdrawals menu"""
    from bot.handlers.admin.panel import handle_admin_panel_button
    
    await handle_admin_panel_button(message, session, **data)
