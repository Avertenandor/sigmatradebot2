"""
User Support Handler - УПРОЩЕННАЯ ВЕРСИЯ с Reply Keyboards
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from bot.keyboards.reply import support_keyboard
from bot.states.support_states import SupportStates

router = Router(name="support")


@router.message(F.text == "💬 Поддержка")
async def handle_support_menu(
    message: Message,
    state: FSMContext,
    user: User,
) -> None:
    """Show support menu."""
    await state.clear()
    
    text = (
        f"💬 *Служба поддержки*\n\n"
        f"Выберите действие из меню ниже:"
    )
    
    await message.answer(
        text,
        reply_markup=support_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text == "✉️ Создать обращение")
async def handle_create_ticket(
    message: Message,
    state: FSMContext,
    user: User,
) -> None:
    """Start ticket creation."""
    text = (
        f"✉️ *Создать обращение*\n\n"
        f"Опишите вашу проблему или вопрос.\n"
        f"Отправьте текстовое сообщение.\n\n"
        f"Для отмены нажмите '📊 Главное меню'"
    )
    
    await state.set_state(SupportStates.waiting_for_message)
    await message.answer(text, parse_mode="Markdown")


@router.message(SupportStates.waiting_for_message)
async def process_ticket_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    """Process ticket message."""
    from bot.utils.menu_buttons import is_menu_button
    
    # Check if user pressed menu button
    if is_menu_button(message.text):
        await state.clear()
        return
    
    # Save ticket to database
    from app.services.support_service import SupportService
    from app.models.enums import SupportCategory, SupportStatus
    
    support_service = SupportService(session)
    
    try:
        ticket = await support_service.create_ticket(
            user_id=user.id,
            category=SupportCategory.OTHER,
            subject="Обращение от пользователя",
            message=message.text,
        )
        
        await state.clear()
        
        text = (
            f"✅ *Обращение создано!*\n\n"
            f"Номер: `#{ticket.id}`\n"
            f"Статус: Открыто\n\n"
            f"Мы ответим вам в ближайшее время."
        )
        
        await message.answer(text, parse_mode="Markdown")
        
        # Notify admins
        from app.config.settings import settings
        from bot.main import bot_instance
        
        if bot_instance:
            admin_text = (
                f"🆕 *Новое обращение #{ticket.id}*\n\n"
                f"От: @{user.username or 'пользователь'} (`{user.telegram_id}`)\n"
                f"Текст: {message.text}"
            )
            
            for admin_id in settings.get_admin_ids():
                try:
                    await bot_instance.send_message(
                        admin_id,
                        admin_text,
                        parse_mode="Markdown"
                    )
                except:
                    pass
        
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ Ошибка создания обращения: {e}")


@router.message(F.text == "📋 Мои обращения")
async def handle_my_tickets(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    """Show user's tickets."""
    from app.services.support_service import SupportService
    
    support_service = SupportService(session)
    tickets = await support_service.get_user_tickets(user.id)
    
    if not tickets:
        text = "📋 У вас пока нет обращений"
    else:
        text = "📋 *Ваши обращения:*\n\n"
        
        for ticket in tickets[:10]:  # Show last 10
            status_emoji = {
                "open": "🔵",
                "in_progress": "🟡",
                "answered": "🟢",
                "closed": "⚫"
            }.get(ticket.status, "⚪")
            
            text += (
                f"{status_emoji} #{ticket.id} - {ticket.subject}\n"
                f"   Создано: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
    
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "❓ FAQ")
async def handle_faq(
    message: Message,
) -> None:
    """Show FAQ."""
    text = (
        f"❓ *Часто задаваемые вопросы*\n\n"
        f"*Q: Как сделать депозит?*\n"
        f"A: Выберите '💰 Депозит' → Выберите уровень → Отправьте USDT на указанный адрес\n\n"
        f"*Q: Как вывести средства?*\n"
        f"A: Выберите '💸 Вывод' → Укажите сумму → Подтвердите финансовым паролем\n\n"
        f"*Q: Как работает реферальная программа?*\n"
        f"A: Пригласите друга по своей реферальной ссылке → Получайте % от его депозитов\n\n"
        f"*Q: Что делать если забыл финансовый пароль?*\n"
        f"A: Обратитесь в поддержку через '✉️ Создать обращение'\n\n"
        f"Для других вопросов создайте обращение в поддержку."
    )
    
    await message.answer(text, parse_mode="Markdown")

