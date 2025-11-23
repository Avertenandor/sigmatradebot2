"""
Master key management handler.

Allows super admin (telegram_id: 1040687384) to get and regenerate master key.
Similar to @BotFather token management.

FULL FUNCTIONALITY:
- Show master key menu with current status
- Generate new master key (with confirmation)
- Show current key status (hashed, cannot be recovered)
- Cancel operation
- Security logging for all actions
- Role-based access control
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.admin_service import AdminService
from app.services.admin_log_service import AdminLogService

# SUPER_ADMIN_TELEGRAM_ID - only this user can manage master keys
SUPER_ADMIN_TELEGRAM_ID = 1040687384

router = Router()


def is_super_admin(telegram_id: int | None) -> bool:
    """
    Check if user is the super admin.
    
    Args:
        telegram_id: Telegram user ID
        
    Returns:
        True if user is super admin
    """
    return telegram_id == SUPER_ADMIN_TELEGRAM_ID


def master_key_keyboard(has_key: bool = False) -> InlineKeyboardMarkup:
    """
    Build master key management keyboard.
    
    Args:
        has_key: Whether admin has master key set
        
    Returns:
        InlineKeyboardMarkup with options
    """
    buttons = []
    
    if has_key:
        buttons.append([
            InlineKeyboardButton(
                text="📋 Статус текущего ключа",
                callback_data="master_key_status"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text="🔄 Сгенерировать новый ключ" if has_key else "✨ Создать мастер-ключ",
            callback_data="master_key_confirm_regenerate" if has_key else "master_key_regenerate"
        )
    ])
    
    buttons.append([
        InlineKeyboardButton(
            text="◀️ Назад в главное меню",
            callback_data="master_key_cancel"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text == "🔑 Управление мастер-ключом")
async def show_master_key_menu(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Show master key management menu.
    
    Only accessible to super admin (telegram_id: 1040687384).
    NOTE: This handler does NOT require master key authentication
    because it's used to GET the master key.
    
    SECURITY:
    - Checks telegram_id == SUPER_ADMIN_TELEGRAM_ID
    - Verifies admin exists in database
    - Verifies role == super_admin
    - Logs all access attempts
    """
    telegram_id = message.from_user.id if message.from_user else None
    
    # SECURITY CHECK 1: Only super admin by telegram_id
    if not is_super_admin(telegram_id):
        logger.warning(
            f"[SECURITY] Unauthorized master key access attempt from user {telegram_id}"
        )
        await message.answer(
            "❌ Доступ запрещен.\n\n"
            "Эта функция доступна только главному администратору."
        )
        return
    
    # SECURITY CHECK 2: Verify user is actually an admin in database
    admin_service = AdminService(session)
    admin = await admin_service.get_admin_by_telegram_id(telegram_id)
    
    if not admin:
        logger.error(
            f"[SECURITY] User {telegram_id} tried to access master key "
            f"but not found in admins table"
        )
        await message.answer("❌ Администратор не найден в базе данных")
        return
    
    # SECURITY CHECK 3: Verify role is super_admin
    if admin.role != "super_admin":
        logger.warning(
            f"[SECURITY] User {telegram_id} tried to access master key "
            f"but role is {admin.role}, not super_admin"
        )
        await message.answer(
            "❌ Доступ запрещен.\n\n"
            "Требуется роль: super_admin\n"
            f"Ваша роль: {admin.role}"
        )
        return
    
    # SECURITY CHECK 4: Verify admin is not blocked
    if admin.is_blocked:
        logger.warning(
            f"[SECURITY] Blocked admin {telegram_id} tried to access master key"
        )
        await message.answer(
            "❌ Доступ запрещен.\n\n"
            "Ваш аккаунт администратора заблокирован."
        )
        return
    
    await state.clear()
    
    # Check if master key exists
    has_master_key = admin.master_key is not None and admin.master_key != ""
    
    # Build message
    text_lines = [
        "🔑 **Управление мастер-ключом**",
        "",
    ]
    
    if has_master_key:
        text_lines.extend([
            "✅ **Статус:** Мастер-ключ установлен",
            "",
            "Мастер-ключ используется для:",
            "• Входа в админ-панель",
            "• Подтверждения критических операций",
            "• Управления другими администраторами",
            "",
            "⚠️ **Важно:**",
            "• Ключ хранится в зашифрованном виде",
            "• Восстановление невозможно",
            "• При потере - создайте новый",
            "",
            "Выберите действие:"
        ])
    else:
        text_lines.extend([
            "⚠️ **Статус:** Мастер-ключ не установлен",
            "",
            "Для доступа к админ-панели необходимо",
            "создать мастер-ключ.",
            "",
            "Мастер-ключ будет использоваться для:",
            "• Входа в админ-панель",
            "• Подтверждения критических операций",
            "• Управления другими администраторами",
            "",
            "Нажмите кнопку ниже для создания."
        ])
    
    text = "\n".join(text_lines)
    
    # Log access
    logger.info(
        f"[MASTER_KEY] Super admin {telegram_id} opened master key menu "
        f"(has_key={has_master_key})"
    )
    
    await message.answer(
        text,
        reply_markup=master_key_keyboard(has_key=has_master_key),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "master_key_status")
async def show_master_key_status(
    callback: CallbackQuery,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Show current master key status.
    
    Cannot show actual key (it's hashed), but shows:
    - Key exists
    - When it was last changed (if tracked)
    - Security information
    """
    telegram_id = callback.from_user.id if callback.from_user else None
    
    if not is_super_admin(telegram_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    
    admin_service = AdminService(session)
    admin = await admin_service.get_admin_by_telegram_id(telegram_id)
    
    if not admin or not admin.master_key:
        await callback.message.edit_text(
            "⚠️ **Мастер-ключ не установлен**\n\n"
            "Используйте кнопку 'Создать мастер-ключ' для генерации.",
            parse_mode="Markdown",
            reply_markup=master_key_keyboard(has_key=False)
        )
        return
    
    # Build status message
    text_lines = [
        "📋 **Статус мастер-ключа**",
        "",
        "✅ **Ключ установлен:** Да",
        f"🔐 **Хеш:** `{admin.master_key[:20]}...`",
        "",
        "⚠️ **Безопасность:**",
        "• Ключ хранится в зашифрованном виде (bcrypt)",
        "• Восстановление исходного ключа невозможно",
        "• При потере - необходимо создать новый",
        "",
        "🔄 **Смена ключа:**",
        "• Старый ключ перестанет работать",
        "• Новый ключ будет показан один раз",
        "• Сохраните его в надежном месте",
    ]
    
    text = "\n".join(text_lines)
    
    logger.info(f"[MASTER_KEY] Super admin {telegram_id} viewed key status")
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=master_key_keyboard(has_key=True)
    )


@router.callback_query(F.data == "master_key_confirm_regenerate")
async def confirm_regenerate_master_key(
    callback: CallbackQuery,
    **data: Any,
) -> None:
    """
    Ask for confirmation before regenerating master key.
    
    This is a critical operation that will invalidate the old key.
    """
    telegram_id = callback.from_user.id if callback.from_user else None
    
    if not is_super_admin(telegram_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    
    text = (
        "⚠️ **ВНИМАНИЕ: Критическая операция**\n\n"
        "Вы собираетесь сгенерировать новый мастер-ключ.\n\n"
        "**Последствия:**\n"
        "• Старый ключ перестанет работать\n"
        "• Потребуется использовать новый ключ\n"
        "• Новый ключ будет показан только один раз\n\n"
        "**Вы уверены?**"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да, сгенерировать новый ключ",
                callback_data="master_key_regenerate"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="master_key_cancel_regenerate"
            )
        ]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "master_key_regenerate")
async def regenerate_master_key(
    callback: CallbackQuery,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Generate new master key for super admin.
    
    CRITICAL OPERATION:
    - Generates new random key (32 bytes = 256 bits)
    - Hashes with bcrypt
    - Updates admin record
    - Shows key to user (ONLY ONCE)
    - Logs action for security audit
    """
    telegram_id = callback.from_user.id if callback.from_user else None
    
    if not is_super_admin(telegram_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await callback.answer("Генерация нового ключа...")
    
    admin_service = AdminService(session)
    admin = await admin_service.get_admin_by_telegram_id(telegram_id)
    
    if not admin:
        await callback.message.edit_text("❌ Администратор не найден")
        return
    
    # Check if this is first key or regeneration
    is_first_key = admin.master_key is None or admin.master_key == ""
    
    # Generate new master key
    plain_master_key = admin_service.generate_master_key()
    hashed_master_key = admin_service.hash_master_key(plain_master_key)
    
    # Update admin with new master key
    admin.master_key = hashed_master_key
    await session.commit()
    
    # Log action for security audit
    action_type = "MASTER_KEY_CREATED" if is_first_key else "MASTER_KEY_REGENERATED"
    logger.warning(
        f"[SECURITY] {action_type} for super admin {telegram_id} (admin_id: {admin.id})"
    )
    
    # Log to admin_actions table
    try:
        admin_log_service = AdminLogService(session)
        await admin_log_service.log_action(
            admin_id=admin.id,
            action_type=action_type,
            details={
                "telegram_id": telegram_id,
                "is_first_key": is_first_key,
            }
        )
        await session.commit()
    except Exception as e:
        logger.error(f"Failed to log master key action: {e}")
    
    # Show new key to user (ONLY ONCE!)
    text_lines = [
        "✅ **Новый мастер-ключ сгенерирован!**" if not is_first_key else "✅ **Мастер-ключ создан!**",
        "",
        "🔑 **Ваш мастер-ключ:**",
        f"`{plain_master_key}`",
        "",
        "⚠️ **КРИТИЧЕСКИ ВАЖНО:**",
        "• **Сохраните этот ключ в безопасном месте**",
        "• Ключ показывается **только один раз**",
        "• Если вы потеряете ключ, придется создать новый",
        "• Старый ключ больше не будет работать" if not is_first_key else "• Используйте его для входа в админ-панель",
        "",
        "📝 **Рекомендации:**",
        "• Сохраните в менеджере паролей",
        "• Не храните в открытом виде",
        "• Не передавайте третьим лицам",
        "",
        "Используйте этот ключ для входа в админ-панель."
    ]
    
    text = "\n".join(text_lines)
    
    await callback.message.edit_text(text, parse_mode="Markdown")
    
    # Send key in separate message for easy copying
    await callback.message.answer(
        f"📋 **Мастер-ключ для копирования:**\n\n`{plain_master_key}`",
        parse_mode="Markdown"
    )
    
    # Send instructions
    await callback.message.answer(
        "ℹ️ **Как использовать:**\n\n"
        "1. Нажмите кнопку '👑 Админ-панель' в главном меню\n"
        "2. Введите мастер-ключ когда система попросит\n"
        "3. Получите доступ к админ-функциям\n\n"
        "Для возврата в главное меню используйте кнопку ниже.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="master_key_cancel")]
        ])
    )


@router.callback_query(F.data == "master_key_cancel_regenerate")
async def cancel_regenerate(
    callback: CallbackQuery,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Cancel master key regeneration and return to menu."""
    telegram_id = callback.from_user.id if callback.from_user else None
    
    if not is_super_admin(telegram_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await callback.answer("Отменено")
    
    admin_service = AdminService(session)
    admin = await admin_service.get_admin_by_telegram_id(telegram_id)
    
    has_key = admin and admin.master_key is not None and admin.master_key != ""
    
    await callback.message.edit_text(
        "❌ Генерация нового ключа отменена.\n\n"
        "Ваш текущий ключ остался без изменений.",
        reply_markup=master_key_keyboard(has_key=has_key)
    )


@router.callback_query(F.data == "master_key_cancel")
async def cancel_master_key_management(
    callback: CallbackQuery,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Cancel master key management and return to main menu.
    """
    telegram_id = callback.from_user.id if callback.from_user else None
    
    if not is_super_admin(telegram_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    await state.clear()
    
    await callback.message.edit_text(
        "◀️ Возврат в главное меню.\n\n"
        "Используйте кнопки ниже для навигации."
    )
    
    logger.info(f"[MASTER_KEY] Super admin {telegram_id} closed master key menu")
