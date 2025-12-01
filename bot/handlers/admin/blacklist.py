"""
Blacklist management handler.

Allows admins to manage user blacklist.
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.services.blacklist_service import BlacklistService
from bot.keyboards.reply import admin_blacklist_keyboard, admin_keyboard, cancel_keyboard
from bot.states.admin import BlacklistStates
from bot.states.admin_states import AdminStates
from bot.utils.admin_utils import clear_state_preserve_admin_token

router = Router()


@router.message(F.text.in_({"🚫 Управление черным списком", "🚫 Управление blacklist"}))
async def show_blacklist(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show blacklist management menu."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    blacklist_service = BlacklistService(session)

    active_count = await blacklist_service.count_active()
    entries = await blacklist_service.get_all_active(limit=10)

    text = (
        f"🚫 **Управление черным списком**\n\nВсего "
        f"заблокировано: {active_count}\n\n"
    )

    if entries:
        text += "**Последние записи:**\n\n"
        for entry in entries:
            from app.models.blacklist import BlacklistActionType

            action_type_text = {
                BlacklistActionType.REGISTRATION_DENIED: "🚫 Отказ в регистрации",
                BlacklistActionType.TERMINATED: "❌ Терминация",
                BlacklistActionType.BLOCKED: "⚠️ Блокировка",
            }.get(entry.action_type, entry.action_type)
            
            status_emoji = "🟢" if entry.is_active else "⚫"
            status_text = "Активна" if entry.is_active else "Неактивна"
            
            created_date = entry.created_at.strftime("%d.%m.%Y %H:%M")
            reason_preview = entry.reason[:60] if entry.reason else 'N/A'
            if entry.reason and len(entry.reason) > 60:
                reason_preview += "..."

            text += (
                f"{status_emoji} **#{entry.id}** - {status_text}\n"
                f"👤 Telegram: {entry.telegram_id or 'N/A'}\n"
                f"📋 Тип: {action_type_text}\n"
                f"📝 Причина: {reason_preview}\n"
                f"📅 Создано: {created_date}\n"
                f"─────────────────────────────\n\n"
            )
        
        text += "\n**Действия:**\n"
        text += "• `Просмотр #ID` - детали записи\n"
        text += "• `Разблокировать #ID` - удалить из черного списка"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_blacklist_keyboard(),
    )


@router.message(F.text == "➕ Добавить в черный список")
async def start_add_to_blacklist(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start adding to blacklist."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    await message.answer(
        "➕ **Добавление в черный список**\n\n"
        "Введите Telegram ID или BSC wallet address:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )

    await state.set_state(BlacklistStates.waiting_for_identifier)


@router.message(BlacklistStates.waiting_for_identifier)
async def process_blacklist_identifier(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Process identifier for blacklist."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    # Check if message is a cancel button
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "❌ Добавление в черный список отменено.",
            reply_markup=admin_blacklist_keyboard(),
        )
        return

    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if message.text and is_menu_button(message.text):
        await clear_state_preserve_admin_token(state)
        return  # Let menu handlers process this

    identifier = message.text.strip()

    # Determine if telegram ID or wallet
    telegram_id = None
    wallet_address = None

    if identifier.startswith("0x") and len(identifier) == 42:
        # Validate BSC address format
        from app.utils.validation import validate_bsc_address
        if validate_bsc_address(identifier, checksum=False):
            wallet_address = identifier.lower()
        else:
            await message.answer(
                "❌ Неверный формат BSC адреса! "
                "Адрес должен начинаться с '0x' и содержать 42 символа.",
                reply_markup=cancel_keyboard(),
            )
            return
    else:
        try:
            telegram_id = int(identifier)
        except ValueError:
            await message.answer(
                "❌ Неверный формат! Введите "
                "числовой Telegram ID или BSC адрес (0x...).",
                reply_markup=cancel_keyboard(),
            )
            return

    # Save to state
    await state.update_data(
        telegram_id=telegram_id,
        wallet_address=wallet_address,
    )

    await message.answer(
        "Введите причину блокировки:",
        reply_markup=cancel_keyboard(),
    )

    await state.set_state(BlacklistStates.waiting_for_reason)


@router.message(BlacklistStates.waiting_for_reason)
async def process_blacklist_reason(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Process blacklist reason."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    # Check if message is a cancel button
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "❌ Добавление в черный список отменено.",
            reply_markup=admin_blacklist_keyboard(),
        )
        return

    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if message.text and is_menu_button(message.text):
        await clear_state_preserve_admin_token(state)
        return  # Let menu handlers process this

    reason = message.text.strip()

    if len(reason) < 5:
        await message.answer(
            "❌ Причина слишком короткая! Минимум 5 символов.",
            reply_markup=cancel_keyboard(),
        )
        return

    data_state = await state.get_data()
    telegram_id = data_state.get("telegram_id")
    wallet_address = data_state.get("wallet_address")

    # Get admin ID
    admin_id = None
    try:
        from app.repositories.admin_repository import AdminRepository

        admin_repo = AdminRepository(session)
        admin = await admin_repo.get_by(telegram_id=message.from_user.id)
        if admin:
            admin_id = admin.id
    except Exception:
        pass

    blacklist_service = BlacklistService(session)

    try:
        entry = await blacklist_service.add_to_blacklist(
            telegram_id=telegram_id,
            wallet_address=wallet_address,
            reason=reason,
            added_by_admin_id=admin_id,
        )

        await session.commit()

        from app.models.blacklist import BlacklistActionType

        action_type_text = {
            BlacklistActionType.REGISTRATION_DENIED: "Отказ в регистрации",
            BlacklistActionType.TERMINATED: "Терминация",
            BlacklistActionType.BLOCKED: "Блокировка",
        }.get(entry.action_type, entry.action_type)

        await message.answer(
            f"✅ **Добавлено в черный список!**\n\n"
            f"ID: #{entry.id}\n"
            f"Telegram ID: {telegram_id or 'N/A'}\n"
            f"Тип: {action_type_text}\n"
            f"Причина: {reason}",
            parse_mode="Markdown",
            reply_markup=admin_blacklist_keyboard(),
        )

    except Exception as e:
        logger.error(f"Error adding to blacklist: {e}")
        await message.answer(
            f"❌ Ошибка: {e}",
            reply_markup=admin_blacklist_keyboard(),
        )

    await clear_state_preserve_admin_token(state)


@router.message(F.text == "🗑️ Удалить из черного списка")
async def start_remove_from_blacklist(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start removing from blacklist."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    await message.answer(
        "🗑️ **Удаление из черного списка**\n\n"
        "Введите Telegram ID или wallet address для удаления:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )

    await state.set_state(BlacklistStates.waiting_for_removal_identifier)


@router.message(BlacklistStates.waiting_for_removal_identifier)
async def process_blacklist_removal(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Process blacklist removal."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    # Check if message is a cancel button
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "❌ Удаление из черного списка отменено.",
            reply_markup=admin_blacklist_keyboard(),
        )
        return

    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if message.text and is_menu_button(message.text):
        await clear_state_preserve_admin_token(state)
        return  # Let menu handlers process this

    identifier = message.text.strip()

    telegram_id = None
    wallet_address = None

    if identifier.startswith("0x") and len(identifier) == 42:
        # Validate BSC address format
        from app.utils.validation import validate_bsc_address
        if validate_bsc_address(identifier, checksum=False):
            wallet_address = identifier.lower()
        else:
            await message.answer(
                "❌ Неверный формат BSC адреса! "
                "Адрес должен начинаться с '0x' и содержать 42 символа.",
                reply_markup=admin_blacklist_keyboard(),
            )
            await clear_state_preserve_admin_token(state)
            return
    else:
        try:
            telegram_id = int(identifier)
        except ValueError:
            await message.answer(
                "❌ Неверный формат! Введите "
                "числовой Telegram ID или BSC адрес (0x...).",
                reply_markup=admin_blacklist_keyboard(),
            )
            await clear_state_preserve_admin_token(state)
            return

    blacklist_service = BlacklistService(session)

    success = await blacklist_service.remove_from_blacklist(
        telegram_id=telegram_id,
        wallet_address=wallet_address,
    )

    await session.commit()

    if success:
        await message.answer(
            "✅ **Удалено из черного списка!**\n\n"
            "Пользователь снова может использовать бота.",
            parse_mode="Markdown",
            reply_markup=admin_blacklist_keyboard(),
        )
    else:
        await message.answer(
            "❌ Запись не найдена в черном списке.",
            reply_markup=admin_blacklist_keyboard(),
        )

    await clear_state_preserve_admin_token(state)


@router.message(F.text.regexp(r'^Просмотр #(\d+)$'))
async def handle_view_blacklist_entry(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """View blacklist entry details."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    import re
    match = re.match(r'^Просмотр #(\d+)$', message.text)
    if not match:
        await message.answer("❌ Неверный формат. Используйте: `Просмотр #ID`")
        return
    
    entry_id = int(match.group(1))
    
    from app.repositories.blacklist_repository import BlacklistRepository
    from app.models.blacklist import BlacklistActionType
    from bot.keyboards.reply import admin_blacklist_keyboard
    
    blacklist_repo = BlacklistRepository(session)
    entry = await blacklist_repo.get_by_id(entry_id)
    
    if not entry:
        await message.answer(
            f"❌ Запись #{entry_id} не найдена.",
            reply_markup=admin_blacklist_keyboard(),
        )
        return
    
    action_type_text = {
        BlacklistActionType.REGISTRATION_DENIED: "🚫 Отказ в регистрации",
        BlacklistActionType.TERMINATED: "❌ Терминация",
        BlacklistActionType.BLOCKED: "⚠️ Блокировка",
    }.get(entry.action_type, entry.action_type)
    
    status_emoji = "🟢" if entry.is_active else "⚫"
    status_text = "Активна" if entry.is_active else "Неактивна"
    
    added_by_text = "Система"
    if entry.added_by_admin_id:
        from app.repositories.admin_repository import AdminRepository
        admin_repo = AdminRepository(session)
        admin = await admin_repo.get_by_id(entry.added_by_admin_id)
        if admin:
            added_by_text = f"@{admin.username or 'N/A'} (ID: {admin.id})"
        else:
            added_by_text = f"Admin ID: {entry.added_by_admin_id}"
    
    text = (
        f"📋 **Запись черного списка #{entry.id}**\n\n"
        f"{status_emoji} Статус: {status_text}\n"
        f"👤 Telegram ID: {entry.telegram_id or 'N/A'}\n"
        f"💳 Wallet: {entry.wallet_address or 'N/A'}\n"
        f"📋 Тип действия: {action_type_text}\n"
        f"📝 Причина: {entry.reason or 'N/A'}\n"
        f"👨‍💼 Добавил: {added_by_text}\n"
        f"📅 Создано: {entry.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"🔄 Обновлено: {entry.updated_at.strftime('%d.%m.%Y %H:%M')}\n"
    )
    
    # Show appeal deadline if BLOCKED
    if entry.action_type == BlacklistActionType.BLOCKED.value:
        if entry.appeal_deadline:
            deadline_str = entry.appeal_deadline.strftime('%d.%m.%Y %H:%M')
            text += f"⏰ Срок апелляции: {deadline_str}\n"
        else:
            text += "⏰ Срок апелляции: не установлен\n"
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_blacklist_keyboard(),
    )


@router.message(F.text.regexp(r'^Разблокировать #(\d+)$'))
async def handle_unban_user(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Unban user from blacklist."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    import re
    match = re.match(r'^Разблокировать #(\d+)$', message.text)
    if not match:
        await message.answer("❌ Неверный формат. Используйте: `Разблокировать #ID`")
        return
    
    entry_id = int(match.group(1))
    
    from app.repositories.blacklist_repository import BlacklistRepository
    from app.services.blacklist_service import BlacklistService
    from bot.keyboards.reply import admin_blacklist_keyboard, confirmation_keyboard
    from bot.states.admin_states import AdminStates
    
    blacklist_repo = BlacklistRepository(session)
    entry = await blacklist_repo.get_by_id(entry_id)
    
    if not entry:
        await message.answer(
            f"❌ Запись #{entry_id} не найдена.",
            reply_markup=admin_blacklist_keyboard(),
        )
        return
    
    # Get user info for confirmation
    user_label = f"Telegram ID: {entry.telegram_id}" if entry.telegram_id else "Wallet: " + (entry.wallet_address or "N/A")
    
    await state.update_data(blacklist_entry_id=entry_id)
    await state.set_state(AdminStates.awaiting_user_to_unban)
    
    await message.answer(
        f"❓ **Подтвердите разблокировку**\n\n"
        f"Пользователь: {user_label}\n"
        f"Тип: {entry.action_type}\n"
        f"Причина: {entry.reason or 'N/A'}\n\n"
        "Пользователь снова сможет использовать бота.\n\n"
        "Подтвердите действие:",
        parse_mode="Markdown",
        reply_markup=confirmation_keyboard(),
    )


@router.message(AdminStates.awaiting_user_to_unban)
async def handle_unban_confirm(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Confirm unban."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        await clear_state_preserve_admin_token(state)
        return
    
    if message.text != "✅ Да":
        from bot.keyboards.reply import admin_blacklist_keyboard
        await message.answer(
            "❌ Разблокировка отменена.",
            reply_markup=admin_blacklist_keyboard(),
        )
        await clear_state_preserve_admin_token(state)
        return
    
    state_data = await state.get_data()
    entry_id = state_data.get("blacklist_entry_id")
    
    if not entry_id:
        from bot.keyboards.reply import admin_blacklist_keyboard
        await message.answer(
            "❌ Ошибка: ID записи потерян.",
            reply_markup=admin_blacklist_keyboard(),
        )
        await clear_state_preserve_admin_token(state)
        return
    
    from app.repositories.blacklist_repository import BlacklistRepository
    from app.services.blacklist_service import BlacklistService
    from bot.keyboards.reply import admin_blacklist_keyboard
    
    blacklist_repo = BlacklistRepository(session)
    entry = await blacklist_repo.get_by_id(entry_id)
    
    if not entry:
        await message.answer(
            f"❌ Запись #{entry_id} не найдена.",
            reply_markup=admin_blacklist_keyboard(),
        )
        await clear_state_preserve_admin_token(state)
        return
    
    # Remove from blacklist
    blacklist_service = BlacklistService(session)
    success = await blacklist_service.remove_from_blacklist(
        telegram_id=entry.telegram_id,
        wallet_address=entry.wallet_address,
    )
    
    await session.commit()
    
    if success:
        # Notify user if possible
        if entry.telegram_id:
            from aiogram import Bot
            bot: Bot = data.get("bot")
            if bot:
                try:
                    await bot.send_message(
                        chat_id=entry.telegram_id,
                        text="✅ Ваш аккаунт разблокирован. Вы снова можете использовать бота.",
                    )
                except Exception as e:
                    logger.warning(f"Failed to notify user about unban: {e}")
        
        await message.answer(
            f"✅ **Пользователь разблокирован!**\n\n"
            f"Запись #{entry_id} удалена из черного списка.",
            parse_mode="Markdown",
            reply_markup=admin_blacklist_keyboard(),
        )
    else:
        await message.answer(
            "❌ Ошибка при удалении из черного списка.",
            reply_markup=admin_blacklist_keyboard(),
        )
    
    await clear_state_preserve_admin_token(state)


@router.message(F.text == "📝 Редактировать тексты")
async def handle_edit_notification_texts(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show notification texts editor menu."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    from app.repositories.system_setting_repository import SystemSettingRepository
    from bot.keyboards.reply import admin_blacklist_keyboard
    
    setting_repo = SystemSettingRepository(session)
    
    # Get current texts or use defaults
    block_text = await setting_repo.get_value(
        "blacklist_block_notification_text",
        default="⚠️ Ваш аккаунт временно заблокирован в нашем сообществе. Вы можете подать апелляцию в течение 3 рабочих дней."
    )
    terminate_text = await setting_repo.get_value(
        "blacklist_terminate_notification_text",
        default="❌ Ваш аккаунт терминирован в нашем сообществе без возможности восстановления."
    )
    
    text = (
        f"📝 **Редактирование текстов уведомлений**\n\n"
        f"**Текущий текст блокировки:**\n{block_text}\n\n"
        f"**Текущий текст терминации:**\n{terminate_text}\n\n"
        f"Выберите текст для редактирования:\n"
        f"• `Изменить текст блокировки`\n"
        f"• `Изменить текст терминации`"
    )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_blacklist_keyboard(),
    )


@router.message(F.text == "Изменить текст блокировки")
async def handle_start_edit_block_text(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start editing block notification text."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    from app.repositories.system_setting_repository import SystemSettingRepository
    from bot.keyboards.reply import cancel_keyboard
    from bot.states.admin_states import AdminStates
    
    setting_repo = SystemSettingRepository(session)
    current_text = await setting_repo.get_value(
        "blacklist_block_notification_text",
        default="⚠️ Ваш аккаунт временно заблокирован в нашем сообществе. Вы можете подать апелляцию в течение 3 рабочих дней."
    )
    
    await state.set_state(AdminStates.awaiting_block_notification_text)
    
    await message.answer(
        f"📝 **Редактирование текста блокировки**\n\n"
        f"Текущий текст:\n{current_text}\n\n"
        f"Введите новый текст уведомления о блокировке:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdminStates.awaiting_block_notification_text)
async def handle_save_block_text(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Save block notification text."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        await clear_state_preserve_admin_token(state)
        return
    
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        from bot.keyboards.reply import admin_blacklist_keyboard
        await message.answer(
            "❌ Редактирование отменено.",
            reply_markup=admin_blacklist_keyboard(),
        )
        return
    
    new_text = message.text.strip()
    if len(new_text) < 10:
        await message.answer("❌ Текст слишком короткий. Минимум 10 символов.")
        return
    
    from app.repositories.system_setting_repository import SystemSettingRepository
    from bot.keyboards.reply import admin_blacklist_keyboard
    
    setting_repo = SystemSettingRepository(session)
    await setting_repo.set_value("blacklist_block_notification_text", new_text)
    await session.commit()
    
    await message.answer(
        f"✅ **Текст блокировки обновлён!**\n\n"
        f"Новый текст:\n{new_text}",
        parse_mode="Markdown",
        reply_markup=admin_blacklist_keyboard(),
    )
    await clear_state_preserve_admin_token(state)


@router.message(F.text == "Изменить текст терминации")
async def handle_start_edit_terminate_text(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start editing terminate notification text."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    from app.repositories.system_setting_repository import SystemSettingRepository
    from bot.keyboards.reply import cancel_keyboard
    from bot.states.admin_states import AdminStates
    
    setting_repo = SystemSettingRepository(session)
    current_text = await setting_repo.get_value(
        "blacklist_terminate_notification_text",
        default="❌ Ваш аккаунт терминирован в нашем сообществе без возможности восстановления."
    )
    
    await state.set_state(AdminStates.awaiting_terminate_notification_text)
    
    await message.answer(
        f"📝 **Редактирование текста терминации**\n\n"
        f"Текущий текст:\n{current_text}\n\n"
        f"Введите новый текст уведомления о терминации:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdminStates.awaiting_terminate_notification_text)
async def handle_save_terminate_text(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Save terminate notification text."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        await clear_state_preserve_admin_token(state)
        return
    
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        from bot.keyboards.reply import admin_blacklist_keyboard
        await message.answer(
            "❌ Редактирование отменено.",
            reply_markup=admin_blacklist_keyboard(),
        )
        return
    
    new_text = message.text.strip()
    if len(new_text) < 10:
        await message.answer("❌ Текст слишком короткий. Минимум 10 символов.")
        return
    
    from app.repositories.system_setting_repository import SystemSettingRepository
    from bot.keyboards.reply import admin_blacklist_keyboard
    
    setting_repo = SystemSettingRepository(session)
    await setting_repo.set_value("blacklist_terminate_notification_text", new_text)
    await session.commit()
    
    await message.answer(
        f"✅ **Текст терминации обновлён!**\n\n"
        f"Новый текст:\n{new_text}",
        parse_mode="Markdown",
        reply_markup=admin_blacklist_keyboard(),
    )
    await clear_state_preserve_admin_token(state)


@router.message(F.text == "👑 Админ-панель")
async def handle_back_to_admin_panel(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Return to admin panel from blacklist menu"""
    from bot.handlers.admin.panel import handle_admin_panel_button
    
    await handle_admin_panel_button(message, session, **data)
