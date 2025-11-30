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
            "🔒 **Почему выплаты заблокированы?**\n"
            "Это защита: если злоумышленник запросил смену пароля, "
            "он не сможет вывести ваши средства без подтверждения.\n\n"
            "✅ **Как разблокировать:**\n"
            "Сделайте любой вывод с новым паролем — блокировка снимется автоматически.\n\n"
            "👉 Используйте '💸 Вывод' для проверки."
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
        "⚠️ **Важно — прочитайте внимательно:**\n\n"
        "1️⃣ Запрос рассматривается администратором (защита от мошенников)\n"
        "2️⃣ Выплаты заблокированы до первого успешного вывода с новым паролем\n"
        "3️⃣ Это защищает ваши средства, если кто-то получил доступ к аккаунту\n\n"
        "📝 Укажите причину восстановления пароля:"
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
    Process recovery reason - show confirmation before creating request.

    Args:
        message: Telegram message
        session: Database session
        user: Current user
        state: FSM state
        **data: Handler data
    """
    from bot.keyboards.reply import finpass_recovery_confirm_keyboard
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

    # Save reason to state and ask for confirmation
    await state.update_data(reason=reason)
    await state.set_state(FinpassRecoveryStates.waiting_for_confirmation)

    text = (
        "📋 **Проверьте вашу заявку:**\n\n"
        f"📝 **Причина:**\n{reason}\n\n"
        "⚠️ **Напоминание:**\n"
        "• После отправки заявки выплаты будут заблокированы\n"
        "• Администратор рассмотрит запрос вручную\n"
        "• Разблокировка произойдет при первом выводе с новым паролем\n\n"
        "Нажмите **✅ Отправить заявку** для подтверждения:"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=finpass_recovery_confirm_keyboard(),
    )


@router.message(FinpassRecoveryStates.waiting_for_confirmation)
async def process_recovery_confirmation(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Process confirmation and create the recovery request.

    Args:
        message: Telegram message
        session: Database session
        user: Current user
        state: FSM state
        **data: Handler data
    """
    from bot.utils.menu_buttons import is_menu_button

    is_admin = data.get("is_admin", False)

    # Handle cancel
    if (
        is_menu_button(message.text)
        or message.text == "❌ Отменить"
        or message.text == "❌ Отмена"
    ):
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

    # Handle confirm
    if message.text != "✅ Отправить заявку":
        await message.answer(
            "❌ Пожалуйста, используйте кнопки ниже:\n"
            "• **✅ Отправить заявку** — подтвердить\n"
            "• **❌ Отменить** — отменить",
            parse_mode="Markdown",
        )
        return

    # Get reason from state
    state_data = await state.get_data()
    reason = state_data.get("reason", "")

    if not reason:
        await state.clear()
        await message.answer(
            "❌ Ошибка: причина не найдена. Попробуйте заново.",
            reply_markup=main_menu_reply_keyboard(user=user, is_admin=is_admin),
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
            "✅ **Заявка на восстановление пароля отправлена!**\n\n"
            f"🔢 Номер заявки: **#{request.id}**\n\n"
            "📬 Что дальше:\n"
            "• Администратор рассмотрит вашу заявку\n"
            "• Вы получите уведомление с новым паролем\n"
            "• После получения пароля — сделайте вывод для разблокировки\n\n"
            "⏱ Обычно рассмотрение занимает до 24 часов.",
            parse_mode="Markdown",
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
                    f"👤 Пользователь: {username_or_id}\n"
                    f"🔢 ID запроса: #{request.id}\n"
                    f"📝 Причина: {reason[:100]}{'...' if len(reason) > 100 else ''}\n\n"
                    f"👉 Для рассмотрения: Админ-панель → 🔑 Восстановление пароля",
                )
            except Exception as e:
                logger.error(f"Failed to notify admins: {e}")

    except ValueError as e:
        await message.answer(
            f"❌ Ошибка: {e}\n\n"
            "Попробуйте позже или обратитесь в поддержку.",
            reply_markup=main_menu_reply_keyboard(user=user, is_admin=is_admin),
        )

    await state.clear()
