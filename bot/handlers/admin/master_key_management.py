"""
Master key management handler.

Allows super admin (telegram_id: 1040687384) to get and regenerate master key.
Similar to @BotFather token management.
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.admin_service import AdminService

# SUPER_ADMIN_TELEGRAM_ID - only this user can manage master keys
SUPER_ADMIN_TELEGRAM_ID = 1040687384

router = Router()


def is_super_admin(telegram_id: int | None) -> bool:
    """Check if user is the super admin."""
    return telegram_id == SUPER_ADMIN_TELEGRAM_ID


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
    """
    telegram_id = message.from_user.id if message.from_user else None
    
    # Strict check - only super admin by telegram_id
    if not is_super_admin(telegram_id):
        logger.warning(
            f"Unauthorized master key access attempt from user {telegram_id}"
        )
        await message.answer("❌ Доступ запрещен. Эта функция доступна только главному администратору.")
        return
    
    # Verify user is actually an admin in database
    admin_service = AdminService(session)
    admin = await admin_service.get_admin_by_telegram_id(telegram_id)
    
    if not admin:
        await message.answer("❌ Администратор не найден в базе данных")
        return
    
    if admin.role != "super_admin":
        logger.warning(
            f"User {telegram_id} tried to access master key management but role is {admin.role}"
        )
        await message.answer("❌ Доступ запрещен. Требуется роль super_admin.")
        return
    
    await state.clear()
    
    # Check if master key exists
    has_master_key = admin.master_key is not None
    
    text = (
        "🔑 **Управление мастер-ключом**\n\n"
    )
    
    if has_master_key:
        text += (
            "✅ Мастер-ключ установлен\n\n"
            "Выберите действие:"
        )
    else:
        text += (
            "⚠️ Мастер-ключ не установлен\n\n"
            "Сгенерировать новый мастер-ключ?"
        )
    
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard_buttons = []
    
    if has_master_key:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="📋 Показать текущий ключ",
                callback_data="master_key_show"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="🔄 Сгенерировать новый ключ",
            callback_data="master_key_regenerate"
        )
    ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="master_key_cancel"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data == "master_key_show")
async def show_current_master_key(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show current master key (if stored in plaintext - which we don't do)."""
    telegram_id = callback.from_user.id if callback.from_user else None
    
    if not is_super_admin(telegram_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    
    # We can't show the key because it's hashed
    # But we can show that it exists
    admin_service = AdminService(session)
    admin = await admin_service.get_admin_by_telegram_id(telegram_id)
    
    if not admin or not admin.master_key:
        await callback.message.answer(
            "⚠️ Мастер-ключ не установлен.\n\n"
            "Используйте кнопку 'Сгенерировать новый ключ' для создания."
        )
        return
    
    await callback.message.answer(
        "⚠️ **Безопасность**\n\n"
        "Мастер-ключ хранится в зашифрованном виде и не может быть восстановлен.\n\n"
        "Если вы потеряли ключ, используйте кнопку 'Сгенерировать новый ключ' "
        "для создания нового. Старый ключ будет заменен."
    )


@router.callback_query(F.data == "master_key_regenerate")
async def regenerate_master_key(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Generate new master key for super admin."""
    telegram_id = callback.from_user.id if callback.from_user else None
    
    if not is_super_admin(telegram_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    
    admin_service = AdminService(session)
    admin = await admin_service.get_admin_by_telegram_id(telegram_id)
    
    if not admin:
        await callback.message.answer("❌ Администратор не найден")
        return
    
    # Generate new master key
    plain_master_key = admin_service.generate_master_key()
    hashed_master_key = admin_service.hash_master_key(plain_master_key)
    
    # Update admin with new master key
    admin.master_key = hashed_master_key
    await session.commit()
    
    logger.info(
        f"Master key regenerated for super admin {telegram_id} (admin_id: {admin.id})"
    )
    
    # Show new key to user (only once!)
    text = (
        "✅ **Новый мастер-ключ сгенерирован!**\n\n"
        f"🔑 Ваш мастер-ключ:\n"
        f"`{plain_master_key}`\n\n"
        "⚠️ **ВАЖНО:**\n"
        "• Сохраните этот ключ в безопасном месте\n"
        "• Ключ показывается только один раз\n"
        "• Если вы потеряете ключ, сгенерируйте новый\n"
        "• Старый ключ больше не будет работать\n\n"
        "Используйте этот ключ для входа в админ-панель."
    )
    
    await callback.message.answer(text, parse_mode="Markdown")
    
    # Also send as separate message for easier copying
    await callback.message.answer(
        f"📋 **Мастер-ключ для копирования:**\n\n`{plain_master_key}`",
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "master_key_cancel")
async def cancel_master_key_management(
    callback: CallbackQuery,
    state: FSMContext,
    **data: Any,
) -> None:
    """Cancel master key management."""
    telegram_id = callback.from_user.id if callback.from_user else None
    
    if not is_super_admin(telegram_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await callback.answer("Отменено")
    await state.clear()
    await callback.message.answer("❌ Управление мастер-ключом отменено")

