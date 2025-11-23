"""
Admin management handler.

Allows super admins to promote/demote other admins.
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.services.admin_service import AdminService
from bot.keyboards.reply import admin_management_keyboard, admin_keyboard, cancel_keyboard
from bot.states.admin import AdminManagementStates

router = Router()


@router.message(F.text == "👥 Управление админами")
async def show_admin_management(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Show admin management menu.

    Args:
        message: Message
        session: Database session
        data: Handler data
    """
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")
    is_super_admin = data.get("is_super_admin", False)
    
    if not is_admin or not admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    # Check if user is super_admin
    if not is_super_admin:
        await message.answer(
            "❌ Только super admin может управлять администраторами!",
            reply_markup=admin_keyboard(),
        )
        return

    admin_service = AdminService(session)
    admins = await admin_service.get_all_admins()

    text = "👥 **Управление администраторами**\n\n"

    for adm in admins:
        role_emoji = {
            "super_admin": "👑",
            "extended_admin": "🔧",
            "admin": "👤",
        }.get(adm.role, "👤")

        # Check if admin has active session
        has_active_session = any(
            session_obj.is_active and not session_obj.is_expired and not session_obj.is_inactive
            for session_obj in adm.sessions
        )

        text += (
            f"{role_emoji} {adm.telegram_id} - {adm.username or 'N/A'}\n"
            f"   Роль: {adm.role}\n"
            f"   Активен: {'✅' if has_active_session else '❌'}\n\n"
        )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_management_keyboard(),
    )


@router.message(F.text == "➕ Добавить админа")
async def start_add_admin(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start adding new admin."""
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")
    is_super_admin = data.get("is_super_admin", False)
    
    if not is_admin or not admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    # Check if user is super_admin
    if not is_super_admin:
        await message.answer(
            "❌ Доступ запрещён!",
            reply_markup=admin_management_keyboard(),
        )
        return

    await message.answer(
        "➕ **Добавление администратора**\n\n"
        "Введите Telegram ID пользователя:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )

    await state.set_state(AdminManagementStates.awaiting_admin_telegram_id)


@router.message(AdminManagementStates.awaiting_admin_telegram_id)
async def process_telegram_id(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Process telegram ID for new admin."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    # Check if message is a cancel button
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "❌ Добавление админа отменено.",
            reply_markup=admin_management_keyboard(),
        )
        return

    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if message.text and is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this

    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Неверный формат! Введите числовой Telegram ID.",
            reply_markup=cancel_keyboard(),
        )
        return

    # Save to state
    await state.update_data(telegram_id=telegram_id)

    await message.answer(
        f"Выберите роль для пользователя `{telegram_id}`:\n\n"
        "Введите одну из ролей:\n"
        "• `admin` - обычный администратор\n"
        "• `extended_admin` - расширенный администратор\n\n"
        "Или используйте кнопку отмены:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )

    await state.set_state(AdminManagementStates.awaiting_admin_role)


@router.message(AdminManagementStates.awaiting_admin_role)
async def process_role(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Process role selection."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    # Check if message is a cancel button
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "❌ Добавление админа отменено.",
            reply_markup=admin_management_keyboard(),
        )
        return

    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if message.text and is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this

    role = message.text.strip().lower()
    
    if role not in ["admin", "extended_admin"]:
        await message.answer(
            "❌ Неверная роль! Введите `admin` или `extended_admin`.",
            reply_markup=cancel_keyboard(),
        )
        return

    data_state = await state.get_data()
    telegram_id = data_state.get("telegram_id")

    if not telegram_id:
        await message.answer(
            "❌ Ошибка: Telegram ID не найден!",
            reply_markup=admin_management_keyboard(),
        )
        await state.clear()
        return

    # Get current admin from data
    admin: Admin | None = data.get("admin")
    is_super_admin = data.get("is_super_admin", False)
    
    if not admin or not is_super_admin:
        await message.answer(
            "❌ Доступ запрещён!",
            reply_markup=admin_management_keyboard(),
        )
        await state.clear()
        return

    # Create admin
    admin_service = AdminService(session)

    try:
        new_admin, master_key, error = await admin_service.create_admin(
            telegram_id=telegram_id,
            role=role,
            created_by=admin.id,
            username=None,  # Will be updated on first interaction
        )

        if error or not new_admin:
            await message.answer(
                f"❌ **Ошибка при создании администратора!**\n\n{error}",
                parse_mode="Markdown",
                reply_markup=admin_management_keyboard(),
            )
            await state.clear()
            return

        await session.commit()

        await message.answer(
            f"✅ **Администратор добавлен!**\n\n"
            f"Telegram ID: `{new_admin.telegram_id}`\n"
            f"Роль: {new_admin.role}\n\n"
            f"Пользователь может войти в админ панель используя /admin",
            parse_mode="Markdown",
            reply_markup=admin_management_keyboard(),
        )

    except Exception as e:
        logger.error(f"Error creating admin: {e}")
        await message.answer(
            f"❌ Ошибка при создании администратора: {e}",
            reply_markup=admin_management_keyboard(),
        )

    await state.clear()


@router.message(F.text == "📋 Список админов")
async def show_admin_list(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show list of admins."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    admin_service = AdminService(session)
    admins = await admin_service.get_all_admins()

    text = "📋 **Список администраторов:**\n\n"

    for adm in admins:
        role_emoji = {
            "super_admin": "👑",
            "extended_admin": "🔧",
            "admin": "👤",
        }.get(adm.role, "👤")

        # Check if admin has active session
        has_active_session = any(
            session_obj.is_active and not session_obj.is_expired and not session_obj.is_inactive
            for session_obj in adm.sessions
        )

        text += (
            f"{role_emoji} {adm.telegram_id} - {adm.username or 'N/A'}\n"
            f"   Роль: {adm.role}\n"
            f"   Активен: {'✅' if has_active_session else '❌'}\n\n"
        )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_management_keyboard(),
    )


@router.message(F.text == "👑 Админ-панель")
async def handle_back_to_admin_panel(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Return to admin panel from management menu"""
    from bot.handlers.admin.panel import handle_admin_panel_button
    
    await handle_admin_panel_button(message, session, **data)
