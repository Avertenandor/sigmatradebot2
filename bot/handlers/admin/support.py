"""
Admin Support Handlers.

Manages technical support tickets for administrators.
"""

from typing import Any

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SupportSender, SupportTicketStatus
from app.services.support_service import SupportService
from bot.keyboards.reply import (
    admin_support_keyboard,
    admin_support_ticket_keyboard,
    cancel_keyboard,
)
from bot.states.admin import AdminSupportStates
from bot.states.admin_states import AdminStates

router = Router(name="admin_support")


from bot.utils.admin_utils import clear_state_preserve_admin_token


@router.message(StateFilter("*"), F.text == "🆘 Техподдержка")
async def handle_admin_support_menu(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show admin support menu."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    await clear_state_preserve_admin_token(state)
    
    text = (
        "🆘 **Техподдержка**\n\n"
        "Управление обращениями пользователей.\n"
        "Выберите действие:"
    )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_support_keyboard(),
    )


@router.message(StateFilter("*"), F.text == "📋 Список обращений")
async def handle_list_tickets(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """List open tickets."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    support_service = SupportService(session)
    pending_tickets = await support_service.list_open_tickets()
    
    if not pending_tickets:
        text = "📋 **Список обращений**\n\nНет активных обращений."
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=admin_support_keyboard(),
        )
        return

    # Pagination logic (basic)
    page = 1
    per_page = 10
    total_tickets = len(pending_tickets)
    import math
    total_pages = math.ceil(total_tickets / per_page)
    
    # Get tickets for current page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_tickets = pending_tickets[start_idx:end_idx]

    text = f"📋 **Список обращений ({total_tickets})**\n\nВыберите обращение:"
    
    from bot.keyboards.reply import admin_ticket_list_keyboard
    keyboard = admin_ticket_list_keyboard(page_tickets, page, total_pages)

    await state.set_state(AdminSupportStates.viewing_list)
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


@router.message(StateFilter("*"), F.text == "📊 Статистика")
async def handle_support_stats(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show support statistics."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    support_service = SupportService(session)
    stats = await support_service.get_support_stats()
    
    text = (
        "📊 **Статистика техподдержки**\n\n"
        f"📝 Всего обращений: **{stats['total']}**\n\n"
        f"🟡 Открыто: **{stats['open']}**\n"
        f"🔵 В работе: **{stats['in_progress']}**\n"
        f"⏳ Ждем ответа: **{stats['waiting_user']}**\n"
        f"⚫ Закрыто: **{stats['closed']}**"
    )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_support_keyboard(),
    )


@router.message(StateFilter("*"), F.text == "🙋‍♂️ Мои задачи")
async def handle_my_tasks(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show tickets assigned to current admin."""
    admin_id = data.get("admin_id")
    if not admin_id:
        return

    support_service = SupportService(session)
    my_tickets = await support_service.get_tickets_by_admin(admin_id)
    
    if not my_tickets:
        await message.answer(
            "🙋‍♂️ **Мои задачи**\n\nУ вас нет активных задач.",
            reply_markup=admin_support_keyboard(),
        )
        return

    text = f"🙋‍♂️ **Мои задачи ({len(my_tickets)})**\n\n"
    
    for ticket in my_tickets[:10]:
        user_label = f"ID: {ticket.user_id}"
        if hasattr(ticket, 'user') and ticket.user:
            if ticket.user.username:
                user_label = f"@{ticket.user.username}"
            elif ticket.user.telegram_id:
                user_label = f"TG: {ticket.user.telegram_id}"
                
        status_emoji = {
            SupportTicketStatus.IN_PROGRESS.value: "🔵",
            SupportTicketStatus.WAITING_USER.value: "⏳",
        }.get(ticket.status, "⚪")
        
        text += (
            f"{status_emoji} **#{ticket.id}** - {user_label}\n"
            f"👉 `Открыть #{ticket.id}`\n\n"
        )
        
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_support_keyboard(),
    )


@router.message(StateFilter("*"), F.text == "◀️ Назад к списку")
async def back_to_list(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Back to ticket list."""
    await handle_list_tickets(message, session, state, **data)


@router.message(F.text.regexp(r'^(?:Открыть |🎫 )#(\d+)'))
async def handle_view_ticket(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """View specific ticket."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    import re
    match = re.search(r'#(\d+)', message.text)
    if not match:
        return
    
    ticket_id = int(match.group(1))
    await show_ticket_details(message, session, state, ticket_id)


async def show_ticket_details(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    ticket_id: int,
) -> None:
    """Show ticket details and set state."""
    support_service = SupportService(session)
    ticket = await support_service.get_ticket_by_id(ticket_id)
    
    if not ticket:
        await message.answer(
            f"❌ Обращение #{ticket_id} не найдено.",
            reply_markup=admin_support_keyboard(),
        )
        return
    
    # Update state
    await state.update_data(current_ticket_id=ticket_id)
    await state.set_state(AdminSupportStates.viewing_ticket)
    
    # Build details
    user_label = f"ID: {ticket.user_id}"
    if hasattr(ticket, 'user') and ticket.user:
        if ticket.user.username:
            user_label = f"@{ticket.user.username} (ID: {ticket.user_id})"
        elif ticket.user.telegram_id:
            user_label = f"TG: {ticket.user.telegram_id} (ID: {ticket.user_id})"
    
    status_text = {
        SupportTicketStatus.OPEN.value: "🟡 Открыто",
        SupportTicketStatus.IN_PROGRESS.value: "🔵 В работе",
        SupportTicketStatus.ANSWERED.value: "🟢 Отвечено",
        SupportTicketStatus.WAITING_USER.value: "⏳ Ожидает ответа",
        SupportTicketStatus.CLOSED.value: "⚫ Закрыто",
    }.get(ticket.status, ticket.status)
    
    assigned_text = "Не назначен"
    if ticket.assigned_admin_id:
        if hasattr(ticket, 'assigned_admin') and ticket.assigned_admin:
            assigned_text = f"@{ticket.assigned_admin.username or 'N/A'}"
        else:
            assigned_text = f"Admin ID: {ticket.assigned_admin_id}"
    
    text = (
        f"📋 **Обращение #{ticket.id}**\n\n"
        f"👤 Пользователь: {user_label}\n"
        f"📊 Статус: {status_text}\n"
        f"👨‍💼 Назначен: {assigned_text}\n"
        f"📅 Создано: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    )
    
    if hasattr(ticket, 'messages') and ticket.messages:
        text += "**Переписка:**\n\n"
        for msg in ticket.messages[-10:]:  # Show last 10 messages
            sender_icon = {
                SupportSender.USER.value: "👤",
                SupportSender.ADMIN.value: "🛠",
                SupportSender.SYSTEM.value: "⚙️",
            }.get(msg.sender, "❓")
            
            msg_date = msg.created_at.strftime("%d.%m %H:%M")
            text += f"{sender_icon} {msg_date}: {msg.text or '[Вложение]'}\n\n"
    else:
        text += "Нет сообщений.\n"
        
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_support_ticket_keyboard(),
    )


@router.message(AdminSupportStates.viewing_ticket, F.text == "📝 Ответить")
async def start_reply_ticket(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start replying to a ticket."""
    state_data = await state.get_data()
    ticket_id = state_data.get("current_ticket_id")
    
    if not ticket_id:
        await message.answer("❌ Ошибка: ID обращения не найден. Вернитесь к списку.")
        return

    await state.set_state(AdminStates.awaiting_support_reply)
    await message.answer(
        f"📝 **Ответ на обращение #{ticket_id}**\n\n"
        "Введите текст ответа:",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown",
    )


@router.message(AdminSupportStates.viewing_ticket, F.text == "✋ Взять в работу")
async def assign_ticket_to_me(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Assign ticket to current admin."""
    admin_id = data.get("admin_id")
    state_data = await state.get_data()
    ticket_id = state_data.get("current_ticket_id")
    
    if not ticket_id or not admin_id:
        return

    support_service = SupportService(session)
    await support_service.assign_to_admin(ticket_id, admin_id)
    await session.commit()
    
    await message.answer("✅ Обращение назначено вам.")
    await show_ticket_details(message, session, state, ticket_id)


@router.message(AdminSupportStates.viewing_ticket, F.text == "🔒 Закрыть")
async def close_ticket_action(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Close current ticket."""
    state_data = await state.get_data()
    ticket_id = state_data.get("current_ticket_id")
    
    if not ticket_id:
        return

    support_service = SupportService(session)
    await support_service.close_ticket(ticket_id)
    await session.commit()
    
    await message.answer(f"✅ Обращение #{ticket_id} закрыто.")
    await show_ticket_details(message, session, state, ticket_id)


@router.message(AdminSupportStates.viewing_ticket, F.text == "↩️ Переоткрыть")
async def reopen_ticket_action(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Reopen current ticket."""
    state_data = await state.get_data()
    ticket_id = state_data.get("current_ticket_id")
    
    if not ticket_id:
        return

    support_service = SupportService(session)
    await support_service.reopen_ticket(ticket_id)
    await session.commit()
    
    await message.answer(f"✅ Обращение #{ticket_id} переоткрыто.")
    await show_ticket_details(message, session, state, ticket_id)


# Handle Reply Text (using existing AdminStates.awaiting_support_reply)
@router.message(AdminStates.awaiting_support_reply)
async def process_support_reply(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Process reply text."""
    if message.text == "❌ Отмена":
        # Go back to ticket view
        state_data = await state.get_data()
        ticket_id = state_data.get("current_ticket_id")
        if ticket_id:
            await show_ticket_details(message, session, state, ticket_id)
        else:
            await handle_list_tickets(message, session, state, **data)
        return

    reply_text = message.text.strip()
    if len(reply_text) < 3:
        await message.answer("❌ Текст слишком короткий.")
        return

    state_data = await state.get_data()
    ticket_id = state_data.get("current_ticket_id")
    admin_id = data.get("admin_id")

    if not ticket_id or not admin_id:
        await message.answer("❌ Ошибка: данные потеряны.")
        await handle_list_tickets(message, session, state, **data)
        return

    support_service = SupportService(session)
    await support_service.add_admin_message(
        ticket_id=ticket_id,
        admin_id=admin_id,
        text=reply_text,
    )
    await session.commit()

    # Notify user
    ticket = await support_service.get_ticket_by_id(ticket_id)
    if ticket:
        from aiogram import Bot
        bot: Bot = data.get("bot")
        if bot:
            target_id = ticket.telegram_id
            if not target_id and ticket.user:
                target_id = ticket.user.telegram_id
            
            if target_id:
                try:
                    from bot.utils.text_utils import escape_markdown
                    safe_reply = escape_markdown(reply_text)
                    await bot.send_message(
                        chat_id=target_id,
                        text=f"📬 **Ответ на обращение #{ticket_id}**\n\n{safe_reply}",
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.warning(f"Failed to notify user: {e}")

    await message.answer(f"✅ Ответ на обращение #{ticket_id} отправлен.")
    await show_ticket_details(message, session, state, ticket_id)
