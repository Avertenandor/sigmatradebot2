"""
Financial password recovery handler.

Allows users to request financial password recovery with admin approval.
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.finpass_recovery_service import FinpassRecoveryService
from bot.keyboards.reply import main_menu_reply_keyboard
from bot.states.finpass_recovery import FinpassRecoveryStates

router = Router()


async def _start_finpass_recovery_flow(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Common logic for starting financial password recovery.

    Args:
        message: Telegram message
        session: Database session
        user: Current user
        state: FSM state
        **data: Handler data
    """
    from bot.keyboards.reply import finpass_recovery_keyboard, main_menu_reply_keyboard
    
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
        
        is_admin = data.get("is_admin", False)
        from app.repositories.blacklist_repository import BlacklistRepository
        blacklist_repo = BlacklistRepository(session)
        blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
        
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=main_menu_reply_keyboard(
                user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
            ),
        )
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
        
        is_admin = data.get("is_admin", False)
        from app.repositories.blacklist_repository import BlacklistRepository
        blacklist_repo = BlacklistRepository(session)
        blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
        
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=main_menu_reply_keyboard(
                user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
            ),
        )
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
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=finpass_recovery_keyboard(),
    )

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
    await _start_finpass_recovery_flow(message, session, user, state, **data)


@router.message(FinpassRecoveryStates.waiting_for_reason)
async def process_recovery_reason(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Process recovery reason.

    Args:
        message: Telegram message
        session: Database session
        user: Current user
        state: FSM state
        **data: Handler data
    """
    # Check if message is a menu button or cancel - if so, clear state
    from bot.utils.menu_buttons import is_menu_button

    is_admin = data.get("is_admin", False)

    if is_menu_button(message.text) or message.text == "❌ Отмена":
        await state.clear()
        blacklist_entry = None
        try:
            from app.repositories.blacklist_repository import BlacklistRepository
            blacklist_repo = BlacklistRepository(session)
            blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
        except Exception:
            pass
        await message.answer(
            "❌ Восстановление пароля отменено.",
            reply_markup=main_menu_reply_keyboard(
                user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
            ),
        )
        return

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

        # Get blacklist_entry for keyboard
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
