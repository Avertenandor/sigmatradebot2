"""
Financial password recovery admin handler.

Allows admins to approve/reject finpass recovery requests using Reply Keyboards.
"""

import re
from typing import Any

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.finpass_recovery_service import FinpassRecoveryService
from app.services.user_service import UserService
from bot.keyboards.reply import (
    admin_finpass_request_actions_keyboard,
    admin_finpass_request_list_keyboard,
    admin_keyboard,
    get_admin_keyboard_from_data,
)
from bot.states.admin import AdminFinpassRecoveryStates
from bot.utils.admin_utils import clear_state_preserve_admin_token

router = Router()


@router.message(StateFilter("*"), F.text == "🔑 Восстановление пароля")
async def show_recovery_requests(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Show pending finpass recovery requests list.
    
    Entry point for the recovery requests section.
    """
    logger.info(f"[ADMIN] show_recovery_requests called for user {message.from_user.id}")
    is_admin = data.get("is_admin", False)
    if not is_admin:
        logger.warning(f"[ADMIN] User {message.from_user.id} tried to access recovery requests but is_admin=False")
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    recovery_service = FinpassRecoveryService(session)
    requests = await recovery_service.get_all_pending()

    logger.info(f"[ADMIN] Found {len(requests)} pending requests")

    if not requests:
        await message.answer(
            "🔑 **Запросы на восстановление пароля**\n\n"
            "Нет ожидающих запросов.",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard_from_data(data),
        )
        await clear_state_preserve_admin_token(state)
        return

    # Pagination logic
    page = 1
    per_page = 10
    import math
    total_pages = math.ceil(len(requests) / per_page)
    
    # Get requests for current page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_requests = requests[start_idx:end_idx]

    text = (
        f"🔑 **Запросы на восстановление пароля**\n\n"
        f"Всего: {len(requests)}\n"
        f"Страница: {page}/{total_pages}\n\n"
        "Выберите запрос для обработки:"
    )

    await state.set_state(AdminFinpassRecoveryStates.viewing_list)
    await state.update_data(current_page=page, total_pages=total_pages)

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_finpass_request_list_keyboard(page_requests, page, total_pages),
    )


@router.message(StateFilter("*"), F.text.regexp(r'^🔑 Запрос #(\d+)'))
async def handle_view_request(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """View specific recovery request details."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    match = re.search(r'#(\d+)', message.text)
    if not match:
        return

    request_id = int(match.group(1))
    await show_request_details(message, session, state, request_id)


def escape_markdown(text: str) -> str:
    """Escape special Markdown characters in user input."""
    if not text:
        return ""
    # Escape Markdown special chars: _ * [ ] ( ) ~ ` > # + - = | { } . !
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


async def show_request_details(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    request_id: int,
) -> None:
    """Show request details and action buttons."""
    try:
        recovery_service = FinpassRecoveryService(session)
        request = await recovery_service.get_request_by_id(request_id)

        if not request:
            await message.answer(
                f"❌ Запрос #{request_id} не найден.",
                reply_markup=get_admin_keyboard_from_data({}),
            )
            # Try to reload list
            await show_recovery_requests(message, session, state)
            return

        user_service = UserService(session)
        user = await user_service.get_user_by_id(request.user_id)

        if user:
            username = escape_markdown(user.username) if user.username else str(user.telegram_id)
            user_label = f"{username} (ID: {user.id})"
            telegram_link = f"TG: {user.telegram_id}"
        else:
            user_label = f"ID: {request.user_id}"
            telegram_link = "TG: Неизвестно"

        # Escape user-provided reason to prevent Markdown parsing errors
        safe_reason = escape_markdown(request.reason or "Не указана")

        text = (
            f"🔑 *Запрос на восстановление #{request.id}*\n\n"
            f"👤 Пользователь: {user_label}\n"
            f"📱 {telegram_link}\n"
            f"📅 Создан: {request.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"📝 *Причина:*\n{safe_reason}\n\n"
            "Выберите действие:"
        )

        await state.update_data(current_request_id=request_id)
        await state.set_state(AdminFinpassRecoveryStates.viewing_request)

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=admin_finpass_request_actions_keyboard(),
        )

    except Exception as e:
        logger.error(f"Error showing request details for #{request_id}: {e}")
        await message.answer(
            "❌ Произошла ошибка при загрузке данных запроса.\n"
            "Попробуйте еще раз или вернитесь к списку.",
            reply_markup=get_admin_keyboard_from_data({}),
        )


@router.message(AdminFinpassRecoveryStates.viewing_request, F.text == "✅ Одобрить запрос")
async def approve_request_action(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Approve the current request."""
    state_data = await state.get_data()
    request_id = state_data.get("current_request_id")
    
    if not request_id:
        await message.answer("❌ Ошибка: ID запроса потерян.")
        await show_recovery_requests(message, session, state, **data)
        return

    # Get admin
    from app.repositories.admin_repository import AdminRepository
    admin_repo = AdminRepository(session)
    admin = await admin_repo.get_by(telegram_id=message.from_user.id)
    
    if not admin:
        await message.answer("❌ Администратор не найден")
        return

    recovery_service = FinpassRecoveryService(session)
    user_service = UserService(session)

    try:
        # Approve in DB
        request = await recovery_service.approve_request(
            request_id=request_id,
            admin_id=admin.id,
            admin_notes="Approved via Admin Panel (Reply)",
        )

        # Generate new password
        import secrets
        import string
        new_password = "".join(
            secrets.choice(string.ascii_letters + string.digits)
            for _ in range(12)
        )

        # Update user
        user = await user_service.get_user_by_id(request.user_id)
        if not user:
            raise ValueError("User not found")

        import bcrypt
        hashed = bcrypt.hashpw(
            new_password.encode(),
            bcrypt.gensalt(rounds=12),
        )
        user.financial_password = hashed.decode()
        user.earnings_blocked = True

        # Notify user
        notification_sent = False
        try:
            logger.info(f"Sending new password to user telegram_id={user.telegram_id}")
            await message.bot.send_message(
                user.telegram_id,
                f"✅ *Ваш запрос на восстановление пароля одобрен!*\n\n"
                f"Новый финансовый пароль: `{new_password}`\n\n"
                f"⚠️ *Важно:*\n"
                f"• Сохраните этот пароль в надёжном месте\n"
                f"• Ваши выплаты заблокированы до первого использования пароля\n\n"
                f"Используйте раздел 'Вывод' для проверки.",
                parse_mode="Markdown",
            )
            notification_sent = True
            logger.info(f"Password notification sent to user {user.telegram_id}")
        except Exception as e:
            logger.error(f"Failed to notify user {user.id} (tg={user.telegram_id}): {e}")

        await recovery_service.mark_sent(
            request_id=request.id,
            admin_id=admin.id,
            admin_notes="Password sent to user" if notification_sent else "Password NOT sent - notification failed",
        )
        await session.commit()

        # Always show password to admin for backup
        if notification_sent:
            await message.answer(
                f"✅ Запрос #{request_id} успешно одобрен.\n"
                f"Новый пароль отправлен пользователю.\n\n"
                f"📋 *Резервная копия (для админа):*\n"
                f"Пароль: `{new_password}`",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard_from_data(data),
            )
        else:
            await message.answer(
                f"⚠️ Запрос #{request_id} одобрен, но НЕ удалось отправить пользователю!\n\n"
                f"📋 *Передайте пароль вручную:*\n"
                f"Пароль: `{new_password}`\n"
                f"Telegram ID: `{user.telegram_id}`",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard_from_data(data),
            )
        # Return to list to process next
        await show_recovery_requests(message, session, state, **data)

    except Exception as e:
        await session.rollback()
        logger.error(f"Error approving request: {e}")
        await message.answer(f"❌ Ошибка при одобрении: {e}")


@router.message(AdminFinpassRecoveryStates.viewing_request, F.text == "❌ Отклонить запрос")
async def reject_request_action(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Reject the current request."""
    state_data = await state.get_data()
    request_id = state_data.get("current_request_id")
    
    if not request_id:
        await message.answer("❌ Ошибка: ID запроса потерян.")
        await show_recovery_requests(message, session, state, **data)
        return

    # Get admin
    from app.repositories.admin_repository import AdminRepository
    admin_repo = AdminRepository(session)
    admin = await admin_repo.get_by(telegram_id=message.from_user.id)
    
    if not admin:
        await message.answer("❌ Администратор не найден")
        return

    recovery_service = FinpassRecoveryService(session)
    user_service = UserService(session)

    try:
        request = await recovery_service.reject_request(
            request_id=request_id,
            admin_id=admin.id,
            admin_notes="Rejected via Admin Panel (Reply)",
        )
        
        user = await user_service.get_user_by_id(request.user_id)
        await session.commit()

        if user:
            try:
                await message.bot.send_message(
                    user.telegram_id,
                    f"❌ **Ваш запрос на восстановление пароля отклонён**\n\n"
                    f"ID запроса: #{request_id}\n"
                    f"Если у вас есть вопросы, обратитесь в поддержку."
                )
            except Exception as e:
                logger.error(f"Failed to notify user {user.id}: {e}")

        await message.answer(
            f"✅ Запрос #{request_id} отклонён.",
        )
        await show_recovery_requests(message, session, state, **data)

    except Exception as e:
        await session.rollback()
        logger.error(f"Error rejecting request: {e}")
        await message.answer(f"❌ Ошибка при отклонении: {e}")


@router.message(StateFilter("*"), F.text == "◀️ Назад к списку")
async def back_to_list_action(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Go back to the list of requests."""
    await show_recovery_requests(message, session, state, **data)


@router.message(AdminFinpassRecoveryStates.viewing_list, F.text.in_({"⬅ Предыдущая", "Следующая ➡"}))
async def handle_pagination(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle list pagination."""
    state_data = await state.get_data()
    current_page = state_data.get("current_page", 1)
    total_pages = state_data.get("total_pages", 1)

    if message.text == "⬅ Предыдущая" and current_page > 1:
        current_page -= 1
    elif message.text == "Следующая ➡" and current_page < total_pages:
        current_page += 1
    
    # Refresh list with new page
    # We need to refactor show_recovery_requests to accept page, or just copy logic here.
    # Let's do a clean refactor by extracting the list logic.
    
    recovery_service = FinpassRecoveryService(session)
    requests = await recovery_service.get_all_pending()
    
    # Re-calculate total pages in case it changed
    per_page = 10
    import math
    total_pages = math.ceil(len(requests) / per_page)
    
    if current_page > total_pages:
        current_page = total_pages
    if current_page < 1:
        current_page = 1

    start_idx = (current_page - 1) * per_page
    end_idx = start_idx + per_page
    page_requests = requests[start_idx:end_idx]

    text = (
        f"🔑 **Запросы на восстановление пароля**\n\n"
        f"Всего: {len(requests)}\n"
        f"Страница: {current_page}/{total_pages}\n\n"
        "Выберите запрос для обработки:"
    )

    await state.update_data(current_page=current_page, total_pages=total_pages)
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_finpass_request_list_keyboard(page_requests, current_page, total_pages),
    )
