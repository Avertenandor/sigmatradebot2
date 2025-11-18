"""
Admin Withdrawals Handler
Handles withdrawal approval and rejection
"""

import re
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
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
from bot.keyboards.reply import admin_withdrawals_keyboard, admin_keyboard
from bot.states.admin_states import AdminStates
from bot.utils.formatters import format_usdt

router = Router(name="admin_withdrawals")


@router.message(F.text == "⏳ Ожидающие выводы")
async def handle_pending_withdrawals(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle pending withdrawals list (admin only)"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    withdrawal_service = WithdrawalService(session)

    try:
        pending_withdrawals = (
            await withdrawal_service.get_pending_withdrawals()
        )

        text = "💸 **Ожидающие заявки на вывод**\n\n"

        if not pending_withdrawals:
            text += "Нет ожидающих заявок."
            await message.answer(
                text,
                parse_mode="Markdown",
                reply_markup=admin_withdrawals_keyboard(),
            )
            return

        text += f"Всего заявок: **{len(pending_withdrawals)}**\n\n"

        for idx, withdrawal in enumerate(pending_withdrawals[:10], 1):
            date = withdrawal.created_at.strftime("%d.%m.%Y %H:%M")

            text += f"**{idx}. Заявка #{withdrawal.id}**\n"
            text += f"💰 Сумма: {format_usdt(withdrawal.amount)} USDT\n"
            text += f"👤 Пользователь ID: {withdrawal.user_id}\n"

            if (
                hasattr(withdrawal, "user")
                and withdrawal.user
                and withdrawal.user.username
            ):
                text += f"📱 @{withdrawal.user.username}\n"

            text += f"💳 Кошелек: `{withdrawal.to_address}`\n"
            text += f"📅 Дата: {date}\n\n"

        if len(pending_withdrawals) > 10:
            text += f"... и еще {len(pending_withdrawals) - 10} заявок\n\n"

        text += "Для одобрения заявки введите: **одобрить <ID>**\n"
        text += "Для отклонения заявки введите: **отклонить <ID>**\n"
        text += "Пример: `одобрить 123` или `отклонить 123`"

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


@router.message(F.text.regexp(r"^одобрить\s+(\d+)$", flags=0))
async def handle_approve_withdrawal(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle approve withdrawal (admin only)"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    # Extract withdrawal ID from message text
    match = re.match(r"^одобрить\s+(\d+)$", message.text.strip(), re.IGNORECASE)
    if not match:
        await message.answer(
            "❌ Неверный формат. Используйте: `одобрить <ID>`",
            reply_markup=admin_withdrawals_keyboard(),
        )
        return

    withdrawal_id = int(match.group(1))

    withdrawal_service = WithdrawalService(session)
    user_service = UserService(session)
    blockchain_service = get_blockchain_service()
    notification_service = NotificationService(session)

    try:
        # Get withdrawal details
        withdrawal = await withdrawal_service.get_withdrawal_by_id(
            withdrawal_id
        )

        if not withdrawal:
            await message.answer(
                "❌ Заявка не найдена",
                reply_markup=admin_withdrawals_keyboard(),
            )
            return

        # Send real blockchain transaction
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
        success, error_msg = await withdrawal_service.approve_withdrawal(
            withdrawal_id, tx_hash
        )

        if not success:
            await message.answer(
                f"❌ Ошибка: {error_msg or 'Неизвестная ошибка'}",
                reply_markup=admin_withdrawals_keyboard(),
            )
            return

        # Send notification to user about withdrawal approval
        user = await user_service.find_by_id(withdrawal.user_id)
        if user:
            await notification_service.notify_withdrawal_processed(
                user.telegram_id, float(withdrawal.amount), tx_hash
            )

        text = (
            f"✅ **Заявка #{withdrawal_id} одобрена**\n\n"
            f"💰 Сумма: {format_usdt(withdrawal.amount)} USDT\n"
            f"👤 Пользователь ID: {withdrawal.user_id}\n"
            f"💳 Кошелек: `{withdrawal.to_address}`\n"
            f"🔗 TX: `{tx_hash}`\n\n"
            "Средства отправлены пользователю."
        )

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=admin_withdrawals_keyboard(),
        )

        # Log admin action
        admin: Admin | None = data.get("admin")
        if admin:
            log_service = AdminLogService(session)
            await log_service.log_withdrawal_approved(
                admin=admin,
                withdrawal_id=withdrawal_id,
                user_id=withdrawal.user_id,
                amount=str(withdrawal.amount),
            )

    except Exception as e:
        await message.answer(
            f"❌ Ошибка при обработке: {str(e)}",
            reply_markup=admin_withdrawals_keyboard(),
        )


@router.message(F.text.regexp(r"^отклонить\s+(\d+)$", flags=0))
async def handle_reject_withdrawal(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle reject withdrawal (admin only)"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    # Extract withdrawal ID from message text
    match = re.match(r"^отклонить\s+(\d+)$", message.text.strip(), re.IGNORECASE)
    if not match:
        await message.answer(
            "❌ Неверный формат. Используйте: `отклонить <ID>`",
            reply_markup=admin_withdrawals_keyboard(),
        )
        return

    withdrawal_id = int(match.group(1))

    withdrawal_service = WithdrawalService(session)
    user_service = UserService(session)
    notification_service = NotificationService(session)

    try:
        # Get withdrawal details
        withdrawal = await withdrawal_service.get_withdrawal_by_id(
            withdrawal_id
        )

        if not withdrawal:
            await message.answer(
                "❌ Заявка не найдена",
                reply_markup=admin_withdrawals_keyboard(),
            )
            return

        success, error_msg = await withdrawal_service.reject_withdrawal(
            withdrawal_id
        )

        if not success:
            await message.answer(
                f"❌ Ошибка: {error_msg or 'Неизвестная ошибка'}",
                reply_markup=admin_withdrawals_keyboard(),
            )
            return

        # Send notification to user about withdrawal rejection
        user = await user_service.find_by_id(withdrawal.user_id)
        if user:
            await notification_service.notify_withdrawal_rejected(
                user.telegram_id, float(withdrawal.amount)
            )

        text = (
            f"❌ **Заявка #{withdrawal_id} отклонена**\n\n"
            f"💰 Сумма: {format_usdt(withdrawal.amount)} USDT\n"
            f"👤 Пользователь ID: {withdrawal.user_id}\n"
            f"💳 Кошелек: `{withdrawal.to_address}`\n\n"
            "Средства возвращены на баланс пользователя."
        )

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=admin_withdrawals_keyboard(),
        )

        # Log admin action
        admin: Admin | None = data.get("admin")
        if admin:
            log_service = AdminLogService(session)
            await log_service.log_withdrawal_rejected(
                admin=admin,
                withdrawal_id=withdrawal_id,
                user_id=withdrawal.user_id,
                reason=None,
            )

    except Exception as e:
        await message.answer(
            f"❌ Ошибка при обработке: {str(e)}",
            reply_markup=admin_withdrawals_keyboard(),
        )


@router.message(F.text == "✅ Одобренные выводы")
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


@router.message(F.text == "❌ Отклоненные выводы")
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
