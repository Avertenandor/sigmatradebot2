"""
Financial password recovery handler.

Allows users to request financial password recovery with admin approval.
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.finpass_recovery_service import FinpassRecoveryService
from bot.keyboards.reply import main_menu_reply_keyboard
from bot.states.finpass_recovery import FinpassRecoveryStates

router = Router()


async def _start_finpass_recovery_flow(
    message_or_callback: Message | CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """
    Common logic for starting financial password recovery.

    Args:
        message_or_callback: Message or CallbackQuery
        session: Database session
        user: Current user
        state: FSM state
    """
    recovery_service = FinpassRecoveryService(session)

    # Check if already has pending request
    pending = await recovery_service.get_pending_by_user(user.id)

    if pending:
        text = (
            "⚠️ **У вас уже есть активный запрос на восстановление пароля**\n\n"
            f"Статус: {pending.status}\n"
            f"Создан: {pending.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            "Дождитесь рассмотрения администратором."
        )
        
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardBuilder()
                .row(
                    InlineKeyboardButton(
                        text="◀️ Назад", callback_data="menu:settings"
                    )
                )
                .as_markup(),
            )
            await message_or_callback.answer()
        else:
            await message_or_callback.answer(text, parse_mode="Markdown")
        return

    # Check if has active recovery (approved but not verified)
    has_active = await recovery_service.has_active_recovery(user.id)

    if has_active:
        text = (
            "✅ **Ваш запрос одобрен!**\n\n"
            "Новый финансовый пароль был отправлен вам в личные сообщения.\n\n"
            "⚠️ **Важно:**\n"
            "• Ваши выплаты заблокированы до первого использования нового пароля\n"
            "• После первого успешного вывода блокировка будет снята автоматически\n\n"
            "Используйте раздел 'Вывод' для проверки нового пароля."
        )
        
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardBuilder()
                .row(
                    InlineKeyboardButton(
                        text="💸 Вывод", callback_data="menu:withdrawal"
                    )
                )
                .row(
                    InlineKeyboardButton(
                        text="◀️ Назад", callback_data="menu:settings"
                    )
                )
                .as_markup(),
            )
            await message_or_callback.answer()
        else:
            await message_or_callback.answer(text, parse_mode="Markdown")
        return

    # Show recovery warning
    text = (
        "🔐 **Восстановление финансового пароля**\n\n"
        "⚠️ **Важно:**\n"
        "• Запрос требует одобрения администратора\n"
        "• На время рассмотрения ваши выплаты будут заблокированы\n"
        "• После одобрения вы получите новый пароль\n\n"
        "Укажите причину восстановления пароля:"
    )
    
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardBuilder()
            .row(
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data="menu:settings"
                )
            )
            .as_markup(),
        )
        await message_or_callback.answer()
    else:
        await message_or_callback.answer(text, parse_mode="Markdown")

    await state.set_state(FinpassRecoveryStates.waiting_for_reason)


@router.message(F.text == "🔑 Восстановить финпароль")
async def start_finpass_recovery_from_button(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Start financial password recovery from menu button.

    Args:
        message: Telegram message
        session: Database session
        user: Current user
        state: FSM state
        **data: Handler data
    """
    await _start_finpass_recovery_flow(message, session, user, state)


@router.callback_query(lambda c: c.data == "menu:finpass_recovery")
async def start_finpass_recovery(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """
    Start financial password recovery from callback (for backward compatibility).

    Args:
        callback: Callback query
        session: Database session
        user: Current user
        state: FSM state
    """
    await _start_finpass_recovery_flow(callback, session, user, state)


@router.message(FinpassRecoveryStates.waiting_for_reason)
async def process_recovery_reason(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """
    Process recovery reason.

    Args:
        message: Telegram message
        session: Database session
        user: Current user
        state: FSM state
    """
    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this

    reason = message.text.strip()

    if len(reason) < 10:
        await message.answer(
            "❌ Причина слишком короткая!\n\n"
            "Пожалуйста, опишите ситуацию подробнее "
            "(минимум 10 символов)."
        )
        return

    # Create recovery request
    recovery_service = FinpassRecoveryService(session)

    try:
        request = await recovery_service.create_recovery_request(
            user_id=user.id,
            reason=reason,
        )

        await session.commit()

        # Get is_admin and blacklist_entry for keyboard
        is_admin = False
        blacklist_entry = None
        try:
            from app.repositories.blacklist_repository import BlacklistRepository
            blacklist_repo = BlacklistRepository(session)
            blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
        except Exception:
            pass
        
        await message.answer(
            "✅ **Запрос на восстановление пароля создан!**\n\n"
            f"ID запроса: #{request.id}\n"
            f"Статус: {request.status}\n\n"
            "Администратор рассмотрит ваш запрос в ближайшее время.\n"
            "Вы получите уведомление о решении.",
            reply_markup=main_menu_reply_keyboard(
                user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
            ),
        )

        # Notify admins
        from app.config.settings import settings

        admin_ids = settings.get_admin_ids()
        if admin_ids:
            from bot.utils.notifications import notify_admins

            try:
                username_or_id = user.username or user.telegram_id
                await notify_admins(
                    message.bot,
                    admin_ids,
                    f"🔐 **Новый запрос на восстановление пароля**\n\n"
                    f"Пользователь: {username_or_id}\n"
                    f"ID запроса: #{request.id}\n"
                    f"Причина: {reason[:100]}...\n\n"
                    f"Для рассмотрения используйте админ панель.",
                )
            except Exception as e:
                logger.error(f"Failed to notify admins: {e}")

    except ValueError as e:
        await message.answer(
            f"❌ Ошибка: {e}\n\n"
            "Попробуйте позже или обратитесь в поддержку."
        )

    await state.clear()
