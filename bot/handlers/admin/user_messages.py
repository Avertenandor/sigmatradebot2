"""
Admin handler for viewing user messages.

Allows admins to view text messages sent by users (with REPLY keyboards).
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.services.user_message_log_service import UserMessageLogService
from app.services.user_service import UserService
from bot.keyboards.reply import (
    admin_keyboard,
    get_admin_keyboard_from_data,
    user_messages_navigation_keyboard,
)
from bot.states.admin import AdminUserMessagesStates
from bot.utils.admin_utils import clear_state_preserve_admin_token

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

    await clear_state_preserve_admin_token(state)

    text = """
📝 **Просмотр сообщений пользователей**

Здесь вы можете просмотреть текстовые сообщения, отправленные пользователями боту.

🔍 **Поиск пользователя:**
• Telegram ID: `1040687384`
• Username: `@username`
• ID пользователя: `123`
• Кошелек: `0x...`

_Введите любой из этих идентификаторов:_
    """.strip()

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard_from_data(data),
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

    # Parse telegram_id or username
    
    # Breakout for financial reports (navigation fix)
    if message.text and "Финансовая" in message.text:
        await clear_state_preserve_admin_token(state)
        from bot.handlers.admin.financials import show_financial_list
        await show_financial_list(message, session, state, **data)
        return

    # Check for cancel/back
    if message.text in ("◀️ Назад в админ-панель", "❌ Отмена"):
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "👑 **Панель администратора**\n\nВыберите действие:",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard_from_data(data),
        )
        return

    user_service = UserService(session)
    user = None
    telegram_id = None
    search_query = message.text.strip()

    # Try to find user by different methods
    if search_query.startswith("@"):
        # Search by username
        username = search_query.lstrip("@")
        user = await user_service.find_by_username(username)
        if user:
            telegram_id = user.telegram_id
    elif search_query.startswith("0x") and len(search_query) == 42:
        # Search by wallet
        user = await user_service.get_by_wallet(search_query)
        if user:
            telegram_id = user.telegram_id
    else:
        # Try as numeric ID
        try:
            numeric_id = int(search_query)
            # Try as telegram_id first
            user = await user_service.get_user_by_telegram_id(numeric_id)
            if user:
                telegram_id = user.telegram_id
            else:
                # Try as user_id
                user = await user_service.get_by_id(numeric_id)
                if user:
                    telegram_id = user.telegram_id
        except ValueError:
            # Try as username without @
            user = await user_service.find_by_username(search_query)
            if user:
                telegram_id = user.telegram_id

    if not user or not telegram_id:
        await message.answer(
            f"⚠️ Пользователь по запросу `{search_query}` не найден.\n\n"
            f"Попробуйте:\n"
            f"• Telegram ID (число)\n"
            f"• @username\n"
            f"• ID пользователя (число)\n"
            f"• Адрес кошелька (0x...)",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard_from_data(data),
        )
        return

    # Get messages
    msg_service = UserMessageLogService(session)
    page = 0
    page_size = 50
    messages, total = await msg_service.get_user_messages(
        telegram_id=telegram_id,
        limit=page_size,
        offset=page * page_size,
    )

    if not messages:
        await message.answer(
            f"📝 **Сообщения пользователя {user.username or telegram_id}**\n\n"
            f"Пользователь еще не отправлял текстовых сообщений боту.\n\n"
            f"_Логируются только текстовые сообщения, не кнопки._",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard_from_data(data),
        )
        await clear_state_preserve_admin_token(state)
        return

    # Format messages
    text_lines = [
        f"📝 **Сообщения пользователя {user.username or telegram_id}**",
        f"Telegram ID: `{telegram_id}`",
        f"Всего сообщений: {total}",
        f"Показано: {min(len(messages), 20)}",
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
    await state.set_state(AdminUserMessagesStates.viewing_messages)
    await state.update_data(
        telegram_id=telegram_id,
        page=page,
        total=total,
        page_size=page_size,
    )

    # Check if there are more pages
    total_pages = (total + page_size - 1) // page_size
    has_prev = page > 0
    has_next = page < total_pages - 1
    is_super_admin = data.get("is_super_admin", False)

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=user_messages_navigation_keyboard(
            has_prev=has_prev,
            has_next=has_next,
            is_super_admin=is_super_admin,
        ),
    )
    logger.info(
        f"Admin {admin.id} viewed messages for user {telegram_id} "
        f"(total: {total}, page: {page})"
    )


@router.message(
    AdminUserMessagesStates.viewing_messages,
    F.text == "⬅️ Предыдущая страница"
)
async def prev_page_user_messages(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show previous page of user messages."""
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin:
        await message.answer("❌ Доступ запрещен")
        return

    # Get state data
    state_data = await state.get_data()
    telegram_id = state_data.get("telegram_id")
    current_page = state_data.get("page", 0)
    total = state_data.get("total", 0)
    page_size = state_data.get("page_size", 50)

    if current_page <= 0:
        await message.answer("📝 Вы уже на первой странице")
        return

    new_page = current_page - 1
    await show_messages_page(
        message, session, state, telegram_id, new_page, page_size, total, admin, **data
    )


@router.message(
    AdminUserMessagesStates.viewing_messages,
    F.text == "➡️ Следующая страница"
)
async def next_page_user_messages(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show next page of user messages."""
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin:
        await message.answer("❌ Доступ запрещен")
        return

    # Get state data
    state_data = await state.get_data()
    telegram_id = state_data.get("telegram_id")
    current_page = state_data.get("page", 0)
    total = state_data.get("total", 0)
    page_size = state_data.get("page_size", 50)

    total_pages = (total + page_size - 1) // page_size
    if current_page >= total_pages - 1:
        await message.answer("📝 Вы уже на последней странице")
        return

    new_page = current_page + 1
    await show_messages_page(
        message, session, state, telegram_id, new_page, page_size, total, admin, **data
    )


async def show_messages_page(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    telegram_id: int,
    page: int,
    page_size: int,
    total: int,
    admin: Admin,
    **data: Any,
) -> None:
    """Show specific page of messages."""
    offset = page * page_size

    # Get messages
    msg_service = UserMessageLogService(session)
    messages, _ = await msg_service.get_user_messages(
        telegram_id=telegram_id,
        limit=page_size,
        offset=offset,
    )

    if not messages:
        await message.answer("📝 Нет сообщений на этой странице")
        return

    # Get user info
    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(telegram_id)

    # Format messages
    total_pages = (total + page_size - 1) // page_size
    text_lines = [
        f"📝 **Сообщения пользователя {user.username if user else telegram_id}**",
        f"Telegram ID: `{telegram_id}`",
        f"Всего сообщений: {total}",
        f"Страница: {page + 1}/{total_pages}",
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

    # Update state
    await state.update_data(page=page)

    # Check pagination
    has_prev = page > 0
    has_next = page < total_pages - 1
    is_super_admin = data.get("is_super_admin", False)

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=user_messages_navigation_keyboard(
            has_prev=has_prev,
            has_next=has_next,
            is_super_admin=is_super_admin,
        ),
    )
    logger.info(
        f"Admin {admin.id} viewed page {page} of messages "
        f"for user {telegram_id}"
    )


@router.message(
    AdminUserMessagesStates.viewing_messages,
    F.text == "🔍 Другой пользователь"
)
async def search_another_user(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Search for another user's messages."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Доступ запрещен")
        return

    await state.set_state(AdminUserMessagesStates.waiting_for_user_id)
    await message.answer(
        "🔍 **Поиск сообщений пользователя**\n\n"
        "Введите Telegram ID, @username или ID пользователя:\n\n"
        "_Например: 1040687384 или @username_",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard_from_data(data),
    )


@router.message(
    AdminUserMessagesStates.viewing_messages,
    F.text == "📊 Статистика"
)
async def show_messages_stats(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show statistics for current user's messages."""
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")

    if not is_admin or not admin:
        await message.answer("❌ Доступ запрещен")
        return

    state_data = await state.get_data()
    telegram_id = state_data.get("telegram_id")

    if not telegram_id:
        await message.answer("❌ Ошибка: не найден ID пользователя")
        return

    # Get user info
    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(telegram_id)

    # Get message stats
    msg_service = UserMessageLogService(session)
    stats = await msg_service.get_user_message_stats(telegram_id)

    username = user.username if user else "N/A"
    text = (
        f"📊 **Статистика сообщений**\n\n"
        f"👤 Пользователь: @{username}\n"
        f"🆔 Telegram ID: `{telegram_id}`\n\n"
        f"📝 Всего сообщений: **{stats.get('total', 0)}**\n"
        f"📅 За сегодня: **{stats.get('today', 0)}**\n"
        f"📆 За неделю: **{stats.get('week', 0)}**\n"
        f"📆 За месяц: **{stats.get('month', 0)}**\n\n"
        f"🕒 Первое сообщение: {stats.get('first_message', 'N/A')}\n"
        f"🕒 Последнее сообщение: {stats.get('last_message', 'N/A')}\n"
    )

    is_super_admin = data.get("is_super_admin", False)
    total = state_data.get("total", 0)
    page = state_data.get("page", 0)
    page_size = state_data.get("page_size", 50)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    has_prev = page > 0
    has_next = page < total_pages - 1

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=user_messages_navigation_keyboard(
            has_prev=has_prev,
            has_next=has_next,
            is_super_admin=is_super_admin,
        ),
    )


@router.message(
    AdminUserMessagesStates.viewing_messages,
    F.text == "🗑 Удалить все сообщения"
)
async def delete_user_messages(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Delete all messages for user."""
    is_admin = data.get("is_admin", False)
    admin: Admin | None = data.get("admin")
    is_super_admin = data.get("is_super_admin", False)

    if not is_admin or not admin:
        await message.answer("❌ Доступ запрещен")
        return

    # Only super admin can delete
    if not is_super_admin:
        await message.answer("❌ Только супер-администратор может удалять сообщения")
        return

    # Get telegram_id from state
    state_data = await state.get_data()
    telegram_id = state_data.get("telegram_id")

    if not telegram_id:
        await message.answer("❌ Ошибка: не найден ID пользователя")
        return

    # Delete messages
    msg_service = UserMessageLogService(session)
    count = await msg_service.delete_all_messages(telegram_id)
    await session.commit()

    await clear_state_preserve_admin_token(state)

    await message.answer(
        f"✅ Все сообщения пользователя `{telegram_id}` удалены.\n\n"
        f"Удалено: {count} сообщений",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard_from_data(data),
    )
    logger.warning(
        f"Admin {admin.id} deleted {count} messages for user {telegram_id}"
    )


@router.message(
    AdminUserMessagesStates.viewing_messages,
    F.text == "◀️ Назад в админ-панель"
)
async def back_to_admin_panel_from_messages(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Return to admin panel from message viewing."""
    await clear_state_preserve_admin_token(state)

    await message.answer(
        "👑 **Панель администратора**\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard_from_data(data),
    )
