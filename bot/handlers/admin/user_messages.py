"""
Admin handler for viewing user messages.

Allows admins to view text messages sent by users.
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.services.user_message_log_service import UserMessageLogService
from app.services.user_service import UserService
from bot.keyboards.inline import (
    back_to_admin_panel_keyboard,
    paginated_user_messages_keyboard,
)
from bot.states.admin import AdminUserMessagesStates

router = Router(name="admin_user_messages")


@router.message(F.text == "📝 Просмотр сообщений пользователей")
async def show_user_messages_menu(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Show user messages menu.

    Only accessible to admins.
    """
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    await state.clear()

    text = """
📝 **Просмотр сообщений пользователей**

Здесь вы можете просмотреть текстовые сообщения, отправленные пользователями боту.

Введите Telegram ID пользователя для просмотра его сообщений.

_Например: 1040687384_
    """.strip()

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=back_to_admin_panel_keyboard(),
    )
    await state.set_state(AdminUserMessagesStates.waiting_for_user_id)
    logger.info(f"Admin {admin.id} opened user messages menu")


@router.message(AdminUserMessagesStates.waiting_for_user_id)
async def process_user_id_for_messages(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Process user ID and show messages."""
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    # Parse telegram_id
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Введите числовой Telegram ID.\n\n"
            "_Например: 1040687384_",
            parse_mode="Markdown",
        )
        return

    # Check if user exists
    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(telegram_id)

    if not user:
        await message.answer(
            f"⚠️ Пользователь с ID `{telegram_id}` не найден в базе.\n\n"
            f"Попробуйте другой ID или вернитесь назад.",
            parse_mode="Markdown",
            reply_markup=back_to_admin_panel_keyboard(),
        )
        return

    # Get messages
    msg_service = UserMessageLogService(session)
    messages, total = await msg_service.get_user_messages(
        telegram_id=telegram_id,
        limit=50,
        offset=0,
    )

    if not messages:
        await message.answer(
            f"📝 **Сообщения пользователя {user.username or telegram_id}**\n\n"
            f"Пользователь еще не отправлял текстовых сообщений боту.\n\n"
            f"_Логируются только текстовые сообщения, не кнопки._",
            parse_mode="Markdown",
            reply_markup=back_to_admin_panel_keyboard(),
        )
        await state.clear()
        return

    # Format messages
    text_lines = [
        f"📝 **Сообщения пользователя {user.username or telegram_id}**",
        f"Telegram ID: `{telegram_id}`",
        f"Всего сообщений: {total}",
        f"Показано: {len(messages)}",
        "",
        "---",
        "",
    ]

    for msg in messages[:20]:  # Show first 20
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        # Truncate long messages
        msg_text = msg.message_text
        if len(msg_text) > 100:
            msg_text = msg_text[:100] + "..."
        text_lines.append(f"🕒 {timestamp}")
        text_lines.append(f"💬 `{msg_text}`")
        text_lines.append("")

    text = "\n".join(text_lines)

    # Save state for pagination
    await state.update_data(
        telegram_id=telegram_id,
        page=0,
        total=total,
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=paginated_user_messages_keyboard(
            telegram_id=telegram_id,
            page=0,
            total=total,
            page_size=50,
        ),
    )
    await state.clear()
    logger.info(
        f"Admin {admin.id} viewed messages for user {telegram_id} "
        f"(total: {total})"
    )


@router.callback_query(F.data.startswith("user_messages_page:"))
async def paginate_user_messages(
    callback: CallbackQuery,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Paginate user messages."""
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    # Parse callback data: user_messages_page:telegram_id:page
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ Неверный формат", show_alert=True)
        return

    telegram_id = int(parts[1])
    page = int(parts[2])
    page_size = 50
    offset = page * page_size

    # Get messages
    msg_service = UserMessageLogService(session)
    messages, total = await msg_service.get_user_messages(
        telegram_id=telegram_id,
        limit=page_size,
        offset=offset,
    )

    if not messages:
        await callback.answer("📝 Нет сообщений на этой странице")
        return

    # Get user info
    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(telegram_id)

    # Format messages
    text_lines = [
        f"📝 **Сообщения пользователя {user.username if user else telegram_id}**",
        f"Telegram ID: `{telegram_id}`",
        f"Всего сообщений: {total}",
        f"Страница: {page + 1}/{(total + page_size - 1) // page_size}",
        "",
        "---",
        "",
    ]

    for msg in messages[:20]:
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        msg_text = msg.message_text
        if len(msg_text) > 100:
            msg_text = msg_text[:100] + "..."
        text_lines.append(f"🕒 {timestamp}")
        text_lines.append(f"💬 `{msg_text}`")
        text_lines.append("")

    text = "\n".join(text_lines)

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=paginated_user_messages_keyboard(
            telegram_id=telegram_id,
            page=page,
            total=total,
            page_size=page_size,
        ),
    )
    await callback.answer()
    logger.info(
        f"Admin {admin.id} viewed page {page} of messages "
        f"for user {telegram_id}"
    )


@router.callback_query(F.data.startswith("delete_user_messages:"))
async def delete_user_messages(
    callback: CallbackQuery,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Delete all messages for user."""
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")
    is_super_admin = data.get("is_super_admin", False)

    if not is_admin or not admin:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    # Only super admin can delete
    if not is_super_admin:
        await callback.answer(
            "❌ Только супер-администратор может удалять сообщения",
            show_alert=True,
        )
        return

    # Parse telegram_id
    telegram_id = int(callback.data.split(":")[1])

    # Delete messages
    msg_service = UserMessageLogService(session)
    count = await msg_service.delete_all_messages(telegram_id)
    await session.commit()

    await callback.answer(
        f"✅ Удалено {count} сообщений пользователя {telegram_id}",
        show_alert=True,
    )
    await callback.message.edit_text(
        f"✅ Все сообщения пользователя `{telegram_id}` удалены.\n\n"
        f"Удалено: {count} сообщений",
        parse_mode="Markdown",
        reply_markup=back_to_admin_panel_keyboard(),
    )
    logger.warning(
        f"Admin {admin.id} deleted {count} messages for user {telegram_id}"
    )

