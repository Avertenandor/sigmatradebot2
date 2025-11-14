"""
Admin Withdrawals Handler
Handles withdrawal approval and rejection
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.withdrawal_service import WithdrawalService
from app.services.user_service import UserService
from app.services.blockchain_service import BlockchainService
from app.services.notification_service import NotificationService
from bot.utils.formatters import format_usdt


router = Router(name="admin_withdrawals")


@router.callback_query(F.data == "admin_pending_withdrawals")
async def handle_pending_withdrawals(
    callback: CallbackQuery,
    session: AsyncSession,
    is_admin: bool = False,
) -> None:
    """Handle pending withdrawals list (admin only)"""
    if not is_admin:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return

    withdrawal_service = WithdrawalService(session)

    try:
        pending_withdrawals = await withdrawal_service.get_pending_withdrawals()

        message = "💸 **Ожидающие заявки на вывод**\n\n"

        if not pending_withdrawals:
            message += "Нет ожидающих заявок."
            buttons = [
                [
                    InlineKeyboardButton(
                        text="◀️ Назад", callback_data="admin_panel"
                    )
                ]
            ]
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback.message.edit_text(
                message, parse_mode="Markdown", reply_markup=keyboard
            )
            await callback.answer()
            return

        message += f"Всего заявок: **{len(pending_withdrawals)}**\n\n"

        for idx, withdrawal in enumerate(pending_withdrawals, 1):
            date = withdrawal.created_at.strftime("%d.%m.%Y %H:%M")

            message += f"**{idx}. Заявка #{withdrawal.id}**\n"
            message += f"💰 Сумма: {format_usdt(withdrawal.amount)} USDT\n"
            message += f"👤 Пользователь ID: {withdrawal.user_id}\n"

            if hasattr(withdrawal, "user") and withdrawal.user and withdrawal.user.username:
                message += f"📱 @{withdrawal.user.username}\n"

            message += f"💳 Кошелек: `{withdrawal.to_address}`\n"
            message += f"📅 Дата: {date}\n\n"

        # Create buttons for first 5 withdrawals
        buttons = []
        display_count = min(len(pending_withdrawals), 5)

        for i in range(display_count):
            withdrawal = pending_withdrawals[i]
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"✅ #{withdrawal.id} Одобрить",
                        callback_data=f"admin_approve_withdrawal_{withdrawal.id}",
                    ),
                    InlineKeyboardButton(
                        text=f"❌ #{withdrawal.id} Отклонить",
                        callback_data=f"admin_reject_withdrawal_{withdrawal.id}",
                    ),
                ]
            )

        buttons.append(
            [
                InlineKeyboardButton(
                    text="◀️ Назад", callback_data="admin_panel"
                )
            ]
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            message, parse_mode="Markdown", reply_markup=keyboard
        )
        await callback.answer()

    except Exception as e:
        await callback.answer(f"❌ Ошибка при загрузке заявок: {str(e)}")


@router.callback_query(F.data.startswith("admin_approve_withdrawal_"))
async def handle_approve_withdrawal(
    callback: CallbackQuery,
    session: AsyncSession,
    is_admin: bool = False,
) -> None:
    """Handle approve withdrawal (admin only)"""
    if not is_admin:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return

    # Extract withdrawal ID from callback data
    withdrawal_id_str = callback.data.replace("admin_approve_withdrawal_", "")
    if not withdrawal_id_str.isdigit():
        await callback.answer("❌ Неверный формат")
        return

    withdrawal_id = int(withdrawal_id_str)

    withdrawal_service = WithdrawalService(session)
    user_service = UserService(session)
    blockchain_service = BlockchainService(session)
    notification_service = NotificationService(session)

    try:
        # Get withdrawal details
        withdrawal = await withdrawal_service.get_withdrawal_by_id(withdrawal_id)

        if not withdrawal:
            await callback.answer("❌ Заявка не найдена")
            return

        # Send real blockchain transaction
        payment_result = await blockchain_service.send_payment(
            withdrawal.to_address, float(withdrawal.amount)
        )

        if not payment_result["success"]:
            error_msg = payment_result.get("error", "Неизвестная ошибка")
            await callback.answer(f"❌ Ошибка отправки: {error_msg}")
            return

        tx_hash = payment_result["tx_hash"]
        result = await withdrawal_service.approve_withdrawal(
            withdrawal_id, tx_hash
        )

        if not result["success"]:
            await callback.answer(f"❌ Ошибка: {result.get('error')}")
            return

        # Send notification to user about withdrawal approval
        user = await user_service.find_by_id(withdrawal.user_id)
        if user:
            await notification_service.notify_withdrawal_processed(
                user.telegram_id, float(withdrawal.amount), tx_hash
            )

        await callback.answer("✅ Заявка одобрена!")

        # Update message
        message = (
            f"✅ **Заявка #{withdrawal_id} одобрена**\n\n"
            f"💰 Сумма: {format_usdt(withdrawal.amount)} USDT\n"
            f"👤 Пользователь ID: {withdrawal.user_id}\n"
            f"💳 Кошелек: `{withdrawal.to_address}`\n"
            f"🔗 TX: `{tx_hash}`\n\n"
            "Средства отправлены пользователю."
        )

        buttons = [
            [
                InlineKeyboardButton(
                    text="📋 Список заявок",
                    callback_data="admin_pending_withdrawals",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Админ-панель", callback_data="admin_panel"
                )
            ],
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            message, parse_mode="Markdown", reply_markup=keyboard
        )

    except Exception as e:
        await callback.answer(f"❌ Ошибка при обработке: {str(e)}")


@router.callback_query(F.data.startswith("admin_reject_withdrawal_"))
async def handle_reject_withdrawal(
    callback: CallbackQuery,
    session: AsyncSession,
    is_admin: bool = False,
) -> None:
    """Handle reject withdrawal (admin only)"""
    if not is_admin:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return

    # Extract withdrawal ID from callback data
    withdrawal_id_str = callback.data.replace("admin_reject_withdrawal_", "")
    if not withdrawal_id_str.isdigit():
        await callback.answer("❌ Неверный формат")
        return

    withdrawal_id = int(withdrawal_id_str)

    withdrawal_service = WithdrawalService(session)
    user_service = UserService(session)
    notification_service = NotificationService(session)

    try:
        # Get withdrawal details
        withdrawal = await withdrawal_service.get_withdrawal_by_id(withdrawal_id)

        if not withdrawal:
            await callback.answer("❌ Заявка не найдена")
            return

        result = await withdrawal_service.reject_withdrawal(withdrawal_id)

        if not result["success"]:
            await callback.answer(f"❌ Ошибка: {result.get('error')}")
            return

        # Send notification to user about withdrawal rejection
        user = await user_service.find_by_id(withdrawal.user_id)
        if user:
            await notification_service.notify_withdrawal_rejected(
                user.telegram_id, float(withdrawal.amount)
            )

        await callback.answer("✅ Заявка отклонена")

        # Update message
        message = (
            f"❌ **Заявка #{withdrawal_id} отклонена**\n\n"
            f"💰 Сумма: {format_usdt(withdrawal.amount)} USDT\n"
            f"👤 Пользователь ID: {withdrawal.user_id}\n"
            f"💳 Кошелек: `{withdrawal.to_address}`\n\n"
            "Средства возвращены на баланс пользователя."
        )

        buttons = [
            [
                InlineKeyboardButton(
                    text="📋 Список заявок",
                    callback_data="admin_pending_withdrawals",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Админ-панель", callback_data="admin_panel"
                )
            ],
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            message, parse_mode="Markdown", reply_markup=keyboard
        )

    except Exception as e:
        await callback.answer(f"❌ Ошибка при обработке: {str(e)}")
