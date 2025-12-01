"""
Admin Management Handler.

Handles admin creation, deletion, and role management.
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.services.admin_service import AdminService
from app.services.admin_log_service import AdminLogService
from bot.keyboards.reply import (
    admin_keyboard,
    admin_management_keyboard,
    cancel_keyboard,
)
from bot.states.admin import AdminManagementStates
from bot.utils.admin_utils import clear_state_preserve_admin_token

router = Router(name="admin_admins")


@router.message(F.text == "👥 Управление админами")
async def show_admin_management(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Show admin management menu.

    Only accessible to super_admin.
    """
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    if not admin.is_super_admin:
        await message.answer(
            "❌ Эта функция доступна только супер-администраторам"
        )
        return

    text = """
👥 **Управление админами**

Выберите действие:
    """.strip()

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_management_keyboard(),
    )


@router.message(F.text == "➕ Добавить админа")
async def handle_create_admin(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Start admin creation process.

    Only accessible to super_admin.
    """
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    if not admin.is_super_admin:
        await message.answer(
            "❌ Эта функция доступна только супер-администраторам"
        )
        return

    await state.set_state(AdminManagementStates.awaiting_admin_telegram_id)
    await message.answer(
        "👤 **Создание нового админа**\n\n"
        "Введите Telegram ID нового админа:",
        parse_mode="Markdown",
    )


@router.message(AdminManagementStates.awaiting_admin_telegram_id)
async def handle_admin_telegram_id(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Handle Telegram ID input for new admin or deletion.

    Args:
        message: Telegram message with Telegram ID
        session: Database session
        state: FSM context
        **data: Handler data
    """
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin or not admin.is_super_admin:
        await message.answer("❌ Доступ запрещен")
        await clear_state_preserve_admin_token(state)
        return

    # Check if cancel
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "❌ Операция отменена.",
            reply_markup=admin_management_keyboard(),
        )
        return

    telegram_id_str = message.text.strip() if message.text else ""

    if not telegram_id_str:
        await message.answer("❌ Telegram ID не может быть пустым")
        return

    try:
        telegram_id = int(telegram_id_str)
    except ValueError:
        await message.answer(
            "❌ Неверный формат Telegram ID. "
            "Введите числовое значение:"
        )
        return

    # Get action from state
    state_data = await state.get_data()
    action = state_data.get("action")

    # If action is delete, process deletion
    if action == "delete":
        await handle_delete_admin_telegram_id(
            message, session, state, **data
        )
        return

    # Otherwise, process creation
    admin_service = AdminService(session)
    existing = await admin_service.get_admin_by_telegram_id(telegram_id)

    if existing:
        await message.answer(
            f"❌ Админ с Telegram ID {telegram_id} уже существует.\n\n"
            "Введите другой Telegram ID или отправьте /cancel для отмены:"
        )
        return

    # Save telegram_id and ask for role
    await state.update_data(new_admin_telegram_id=telegram_id)
    await state.set_state(AdminManagementStates.awaiting_admin_role)

    await message.answer(
        "👤 **Выбор роли**\n\n"
        "Выберите роль для нового админа:\n\n"
        "1️⃣ `admin` - Базовые права\n"
        "2️⃣ `extended_admin` - Расширенные права\n"
        "3️⃣ `super_admin` - Полные права\n\n"
        "Введите номер (1, 2 или 3):",
        parse_mode="Markdown",
    )


@router.message(AdminManagementStates.awaiting_admin_role)
async def handle_admin_role_selection(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Handle role selection for new admin.

    Args:
        message: Telegram message with role selection
        session: Database session
        state: FSM context
        **data: Handler data
    """
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin or not admin.is_super_admin:
        await message.answer("❌ Доступ запрещен")
        return

    role_input = message.text.strip() if message.text else ""

    role_map = {
        "1": "admin",
        "2": "extended_admin",
        "3": "super_admin",
        "admin": "admin",
        "extended_admin": "extended_admin",
        "super_admin": "super_admin",
    }

    role = role_map.get(role_input.lower())

    if not role:
        await message.answer(
            "❌ Неверный выбор роли.\n\n"
            "Введите номер (1, 2 или 3) или название роли:"
        )
        return

    # Get telegram_id from state
    state_data = await state.get_data()
    telegram_id = state_data.get("new_admin_telegram_id")

    if not telegram_id:
        await message.answer("❌ Ошибка: Telegram ID не найден")
        await clear_state_preserve_admin_token(state)
        return

    # Save role and create admin
    await state.update_data(new_admin_role=role)

    # Create admin
    admin_service = AdminService(session)
    new_admin, master_key, error = await admin_service.create_admin(
        telegram_id=telegram_id,
        role=role,
        created_by=admin.id,
        username=None,  # Will be set when admin first logs in
    )

    if error or not new_admin or not master_key:
        await message.answer(
            f"❌ Ошибка при создании админа: {error or 'Неизвестная ошибка'}"
        )
        await clear_state_preserve_admin_token(state)
        return

    # Clear state
    await clear_state_preserve_admin_token(state)

    logger.info(
        f"Admin {admin.id} created new admin {new_admin.id} "
        f"(telegram_id={telegram_id}, role={role})"
    )

    # Log admin creation
    log_service = AdminLogService(session)
    await log_service.log_admin_created(
        admin=admin,
        created_admin_id=new_admin.id,
        created_admin_telegram_id=telegram_id,
        role=role,
    )

    # Send confirmation
    role_display = {
        "admin": "Admin",
        "extended_admin": "Extended Admin",
        "super_admin": "Super Admin",
    }.get(role, role)

    await message.answer(
        f"✅ **Админ успешно создан**\n\n"
        f"Telegram ID: `{telegram_id}`\n"
        f"Роль: `{role_display}`\n\n"
        f"Мастер-ключ отправлен новому админу в Telegram.",
        parse_mode="Markdown",
        reply_markup=admin_management_keyboard(),
    )

    # Send master key to new admin via Telegram
    try:
        bot = message.bot
        master_key_message = (
            "🔐 **Ваш мастер-ключ для доступа к админ-панели**\n\n"
            f"Мастер-ключ: `{master_key}`\n\n"
            "⚠️ **ВАЖНО:**\n"
            "• Сохраните этот ключ в безопасном месте\n"
            "• Не передавайте его третьим лицам\n"
            "• Используйте его для входа в админ-панель\n"
            "• При первом входе введите `/admin` и затем мастер-ключ\n\n"
            "Для входа в админ-панель используйте команду `/admin`."
        )

        await bot.send_message(
            chat_id=telegram_id,
            text=master_key_message,
            parse_mode="Markdown",
        )

        logger.info(
            f"Master key sent to new admin {new_admin.id} "
            f"(telegram_id={telegram_id})"
        )
    except Exception as e:
        logger.error(
            f"Failed to send master key to new admin {new_admin.id}: {e}"
        )
        # Still log the master key for manual sending
        logger.info(
            f"Master key for new admin {new_admin.id} "
            f"(telegram_id={telegram_id}): {master_key}"
        )


@router.message(F.text == "📋 Список админов")
async def handle_list_admins(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Show list of all admins.

    Only accessible to super_admin.
    """
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    if not admin.is_super_admin:
        await message.answer(
            "❌ Эта функция доступна только супер-администраторам"
        )
        return

    admin_service = AdminService(session)
    admins = await admin_service.list_all_admins()

    if not admins:
        await message.answer("📋 Список админов пуст")
        return

    text = "📋 **Список админов**\n\n"

    for idx, a in enumerate(admins, 1):
        role_display = {
            "admin": "Admin",
            "extended_admin": "Extended Admin",
            "super_admin": "Super Admin",
        }.get(a.role, a.role)

        creator_info = ""
        if a.created_by:
            creator = await admin_service.get_admin_by_id(a.created_by)
            if creator:
                creator_info = f" (создан {creator.display_name})"

        text += (
            f"{idx}. {a.display_name}\n"
            f"   ID: `{a.telegram_id}`\n"
            f"   Роль: `{role_display}`{creator_info}\n\n"
        )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_management_keyboard(),
    )


@router.message(F.text == "🗑️ Удалить админа")
async def handle_delete_admin(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Start admin deletion process.

    Only accessible to super_admin.
    """
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    if not admin.is_super_admin:
        await message.answer(
            "❌ Эта функция доступна только супер-администраторам"
        )
        return

    # Get all admins
    admin_service = AdminService(session)
    admins = await admin_service.list_all_admins()

    if not admins:
        await message.answer("📋 Список админов пуст")
        return

    # Check if there's only one super_admin
    super_admins = [a for a in admins if a.is_super_admin]
    if len(super_admins) == 1 and super_admins[0].id == admin.id:
        await message.answer(
            "❌ Нельзя удалить последнего супер-администратора"
        )
        return

    text = "🗑️ **Удаление админа**\n\n"
    text += "Введите Telegram ID админа для удаления:\n\n"
    text += "**Список админов:**\n"

    for idx, a in enumerate(admins, 1):
        role_display = {
            "admin": "Admin",
            "extended_admin": "Extended Admin",
            "super_admin": "Super Admin",
        }.get(a.role, a.role)

        text += f"{idx}. {a.display_name} (ID: `{a.telegram_id}`, {role_display})\n"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )

    await state.set_state(AdminManagementStates.awaiting_admin_telegram_id)
    await state.update_data(action="delete")


async def handle_delete_admin_telegram_id(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Handle Telegram ID input for admin deletion.

    Args:
        message: Telegram message with Telegram ID
        session: Database session
        state: FSM context
        **data: Handler data
    """
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin or not admin.is_super_admin:
        await message.answer("❌ Доступ запрещен")
        await clear_state_preserve_admin_token(state)
        return

    telegram_id_str = message.text.strip() if message.text else ""

    if not telegram_id_str:
        await message.answer("❌ Telegram ID не может быть пустым")
        return

    try:
        telegram_id = int(telegram_id_str)
    except ValueError:
        await message.answer(
            "❌ Неверный формат Telegram ID. "
            "Введите числовое значение:"
        )
        return

    # Get admin to delete
    admin_service = AdminService(session)
    admin_to_delete = await admin_service.get_admin_by_telegram_id(
        telegram_id
    )

    if not admin_to_delete:
        await message.answer(
            f"❌ Админ с Telegram ID {telegram_id} не найден."
        )
        await clear_state_preserve_admin_token(state)
        return

    # Check if trying to delete self
    if admin_to_delete.id == admin.id:
        await message.answer("❌ Нельзя удалить самого себя")
        await clear_state_preserve_admin_token(state)
        return

    # Check if trying to delete last super_admin
    all_admins = await admin_service.list_all_admins()
    super_admins = [a for a in all_admins if a.is_super_admin]
    if admin_to_delete.is_super_admin and len(super_admins) == 1:
        await message.answer(
            "❌ Нельзя удалить последнего супер-администратора"
        )
        await clear_state_preserve_admin_token(state)
        return

    # Delete admin
    deleted = await admin_service.delete_admin(admin_to_delete.id)

    if not deleted:
        await message.answer("❌ Ошибка при удалении админа")
        await clear_state_preserve_admin_token(state)
        return

    # Log admin deletion
    log_service = AdminLogService(session)
    await log_service.log_admin_deleted(
        admin=admin,
        deleted_admin_id=admin_to_delete.id,
        deleted_admin_telegram_id=telegram_id,
    )

    await clear_state_preserve_admin_token(state)

    logger.info(
        f"Admin {admin.id} deleted admin {admin_to_delete.id} "
        f"(telegram_id={telegram_id})"
    )

    await message.answer(
        f"✅ **Админ удален**\n\n"
        f"Telegram ID: `{telegram_id}`\n"
        f"Имя: {admin_to_delete.display_name}",
        parse_mode="Markdown",
        reply_markup=admin_management_keyboard(),
    )


@router.message(F.text == "🛑 Экстренно заблокировать админа")
async def handle_emergency_block_admin(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Start emergency admin blocking process.

    Only accessible to super_admin.
    """
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    if not admin.is_super_admin:
        await message.answer(
            "❌ Эта функция доступна только супер-администраторам"
        )
        return

    # Get all admins
    admin_service = AdminService(session)
    admins = await admin_service.list_all_admins()

    if not admins:
        await message.answer("📋 Список админов пуст")
        return

    # Check if there's only one super_admin
    super_admins = [a for a in admins if a.is_super_admin]
    if len(super_admins) == 1 and super_admins[0].id == admin.id:
        await message.answer(
            "❌ Нельзя заблокировать последнего супер-администратора"
        )
        return

    text = (
        "🛑 **Экстренная блокировка админа**\n\n"
        "⚠️ **ВНИМАНИЕ:** Это действие:\n"
        "• Удалит админа из системы\n"
        "• Заблокирует его Telegram ID (TERMINATED)\n"
        "• Деактивирует все его сессии\n"
        "• Заблокирует его как пользователя (если есть)\n\n"
        "Введите Telegram ID админа для экстренной блокировки:\n\n"
        "**Список админов:**\n"
    )

    for idx, a in enumerate(admins, 1):
        role_display = {
            "admin": "Admin",
            "extended_admin": "Extended Admin",
            "super_admin": "Super Admin",
        }.get(a.role, a.role)

        text += f"{idx}. {a.display_name} (ID: `{a.telegram_id}`, {role_display})\n"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )

    await state.set_state(AdminManagementStates.awaiting_emergency_telegram_id)


@router.message(AdminManagementStates.awaiting_emergency_telegram_id)
async def handle_emergency_block_admin_telegram_id(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Handle Telegram ID input for emergency admin blocking.

    Performs atomic operation:
    1. Add to blacklist (TERMINATED)
    2. Delete admin
    3. Ban user if exists
    """
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin or not admin.is_super_admin:
        await message.answer("❌ Доступ запрещен")
        await clear_state_preserve_admin_token(state)
        return

    telegram_id_str = message.text.strip() if message.text else ""

    if not telegram_id_str:
        await message.answer("❌ Telegram ID не может быть пустым")
        return

    try:
        telegram_id = int(telegram_id_str)
    except ValueError:
        await message.answer(
            "❌ Неверный формат Telegram ID. "
            "Введите числовое значение:"
        )
        return

    # Get admin to block
    admin_service = AdminService(session)
    admin_to_block = await admin_service.get_admin_by_telegram_id(telegram_id)

    if not admin_to_block:
        await message.answer(
            f"❌ Админ с Telegram ID {telegram_id} не найден."
        )
        await clear_state_preserve_admin_token(state)
        return

    # Check if trying to block self
    if admin_to_block.id == admin.id:
        await message.answer("❌ Нельзя заблокировать самого себя")
        await clear_state_preserve_admin_token(state)
        return

    # Check if trying to block last super_admin
    all_admins = await admin_service.list_all_admins()
    super_admins = [a for a in all_admins if a.is_super_admin]
    if admin_to_block.is_super_admin and len(super_admins) == 1:
        await message.answer(
            "❌ Нельзя заблокировать последнего супер-администратора"
        )
        await clear_state_preserve_admin_token(state)
        return

    # Atomic operation: block and delete
    try:
        from app.models.blacklist import BlacklistActionType
        from app.services.blacklist_service import BlacklistService
        from app.repositories.user_repository import UserRepository

        # 1. Add to blacklist (TERMINATED)
        blacklist_service = BlacklistService(session)
        blacklist_entry = await blacklist_service.add_to_blacklist(
            telegram_id=telegram_id,
            reason="Compromised admin account",
            added_by_admin_id=admin.id,
            action_type=BlacklistActionType.TERMINATED,
        )

        # 2. Delete admin (deactivates all sessions)
        deleted = await admin_service.delete_admin(admin_to_block.id)

        if not deleted:
            await message.answer("❌ Ошибка при удалении админа")
            await clear_state_preserve_admin_token(state)
            return

        # 3. Ban user if exists
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(telegram_id)
        if user:
            user.is_banned = True
            await session.flush()

        # Commit all changes atomically
        await session.commit()

        # Log emergency block
        log_service = AdminLogService(session)
        await log_service.log_action(
            admin_id=admin.id,
            action_type="ADMIN_TERMINATED",
            target_user_id=user.id if user else None,
            details={
                "terminated_admin_id": admin_to_block.id,
                "terminated_admin_telegram_id": telegram_id,
                "terminated_admin_role": admin_to_block.role,
                "reason": "Compromised admin account",
                "blacklist_entry_id": blacklist_entry.id,
            },
        )

        await clear_state_preserve_admin_token(state)

        from app.utils.security_logging import log_security_event

        log_security_event(
            "EMERGENCY: Admin terminated",
            {
                "admin_id": admin.id,
                "target_telegram_id": telegram_id,
                "target_admin_id": admin_to_block.id,
                "action_type": "ADMIN_TERMINATED",
                "reason": "Compromised admin account",
                "blacklist_entry_id": blacklist_entry.id,
            }
        )

        # Send security notification
        from app.utils.admin_notifications import notify_security_event

        await notify_security_event(
            "EMERGENCY: Admin Terminated",
            (
                f"Admin {admin.display_name} (ID: {admin.id}) "
                f"terminated admin {admin_to_block.display_name} "
                f"(Telegram ID: {telegram_id}) due to compromised account"
            ),
            priority="critical",
        )

        # Notify all super_admins
        try:
            from app.config.settings import settings
            from aiogram import Bot

            bot = Bot(token=settings.telegram_bot_token)
            notification_text = (
                f"🚨 **Экстренная блокировка админа**\n\n"
                f"Админ {admin.display_name} (ID: {admin.id}) "
                f"экстренно заблокировал админа:\n\n"
                f"• Telegram ID: `{telegram_id}`\n"
                f"• Имя: {admin_to_block.display_name}\n"
                f"• Роль: {admin_to_block.role}\n"
                f"• Причина: Compromised admin account\n\n"
                f"Действия выполнены:\n"
                f"✅ Админ удален из системы\n"
                f"✅ Telegram ID заблокирован (TERMINATED)\n"
                f"✅ Все сессии деактивированы"
            )

            for super_admin in super_admins:
                if super_admin.id != admin.id:
                    try:
                        await bot.send_message(
                            chat_id=super_admin.telegram_id,
                            text=notification_text,
                            parse_mode="Markdown",
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to notify super_admin "
                            f"{super_admin.id}: {e}"
                        )

            await bot.session.close()
        except Exception as e:
            logger.error(f"Failed to send notifications: {e}")

        await message.answer(
            f"✅ **Админ экстренно заблокирован**\n\n"
            f"Telegram ID: `{telegram_id}`\n"
            f"Имя: {admin_to_block.display_name}\n"
            f"Роль: {admin_to_block.role}\n\n"
            f"Выполнено:\n"
            f"✅ Админ удален из системы\n"
            f"✅ Telegram ID заблокирован (TERMINATED)\n"
            f"✅ Все сессии деактивированы\n"
            f"✅ Пользователь забанен (если был зарегистрирован)\n\n"
            f"Все супер-администраторы уведомлены.",
            parse_mode="Markdown",
            reply_markup=admin_management_keyboard(),
        )

    except Exception as e:
        logger.error(f"Error in emergency block: {e}")
        await session.rollback()
        await message.answer(
            f"❌ Ошибка при экстренной блокировке: {e}"
        )
        await clear_state_preserve_admin_token(state)

