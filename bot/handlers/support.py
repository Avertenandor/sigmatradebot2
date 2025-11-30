"""
User Support Handler - УПРОЩЕННАЯ ВЕРСИЯ с Reply Keyboards
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.models.user import User
from bot.keyboards.reply import support_keyboard
from bot.states.support_states import SupportStates
from bot.utils.formatters import escape_md

router = Router(name="support")


@router.message(F.text == "💬 Поддержка")
async def handle_support_menu(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show support menu."""
    await state.clear()

    text = "💬 *Служба поддержки*\n\nВыберите действие из меню ниже:"

    await message.answer(
        text, reply_markup=support_keyboard(), parse_mode="Markdown"
    )


@router.message(F.text == "✉️ Создать обращение")
async def handle_create_ticket(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Start ticket creation.

    R1-7: Supports guest tickets (user_id=None, telegram_id required).
    """
    user: User | None = data.get("user")
    telegram_id = message.from_user.id if message.from_user else None

    # R1-7: Разрешаем гостевые тикеты
    if not telegram_id:
        await message.answer(
            "❌ Системная ошибка. Отправьте /start или попробуйте позже.",
            reply_markup=support_keyboard(),
        )
        return

    text = (
        "✉️ *Создать обращение*\n\n"
        "Опишите вашу проблему или вопрос.\n"
        "Отправьте текстовое сообщение.\n\n"
        "💡 **Совет:** Если вопрос касается финансов, укажите:\n"
        "• ID транзакции (Hash)\n"
        "• Сумму и дату\n\n"
        "Для отмены нажмите '📊 Главное меню'"
    )

    await state.set_state(SupportStates.awaiting_input)
    await message.answer(text, parse_mode="Markdown")


@router.message(SupportStates.awaiting_input)
async def process_ticket_message(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Process ticket message.
    Uses session_factory for short transaction during ticket creation.
    """
    user: User | None = data.get("user")
    from bot.utils.menu_buttons import is_menu_button

    # Check if user pressed menu button
    if is_menu_button(message.text):
        await state.clear()
        return

    # Save ticket to database with SHORT transaction
    from app.models.enums import SupportCategory
    from app.services.support_service import SupportService

    session_factory = data.get("session_factory")
    telegram_id = message.from_user.id if message.from_user else None

    if not telegram_id:
        await state.clear()
        await message.answer("❌ Ошибка: не удалось определить пользователя")
        return

    try:
        if not session_factory:
            # Fallback to old session for backward compatibility
            session = data.get("session")
            if not session:
                await state.clear()
                await message.answer(
                    "❌ Системная ошибка. Отправьте /start или "
                    "обратитесь в поддержку."
                )
                return

            support_service = SupportService(session)
            # Create ticket: use user.id if user exists,
            # otherwise None for guest ticket
            user_id = user.id if user else None
            ticket, error = await support_service.create_ticket(
                user_id=user_id,
                telegram_id=telegram_id if user_id is None else None,
                category=SupportCategory.OTHER,
                initial_message=message.text,
            )
        else:
            # NEW pattern: short transaction
            async with session_factory() as session:
                async with session.begin():
                    support_service = SupportService(session)
                    # Create ticket: use user.id if user exists,
            # otherwise None for guest ticket
                    user_id = user.id if user else None
                    ticket, error = await support_service.create_ticket(
                        user_id=user_id,
                        telegram_id=telegram_id if user_id is None else None,
                        category=SupportCategory.OTHER,
                        initial_message=message.text,
                    )
            # Transaction closed here

        if error or not ticket:
            await message.answer(
                f"❌ Ошибка при создании обращения:\n{error}",
                parse_mode="Markdown",
            )
            await state.clear()
            return

        await state.clear()

        text = (
            f"✅ *Обращение создано!*\n\n"
            f"Номер: `#{ticket.id}`\n"
            f"Статус: Открыто\n\n"
            f"Мы ответим вам в ближайшее время."
        )

        await message.answer(
            text, parse_mode="Markdown", reply_markup=support_keyboard()
        )

        # Notify admins
        from app.config.settings import settings
        from bot.main import bot_instance

        if bot_instance:
            # Format admin notification
            if user:
                username = escape_md(user.username) if user.username else "пользователь"
                admin_text = (
                    f"🆕 *Новое обращение #{ticket.id}*\n\n"
                    f"От: @{username} "
                    f"(`{user.telegram_id}`)\n"
                    f"Текст: {message.text}"
                )
            else:
                # Guest ticket
                username = (
                    escape_md(message.from_user.username)
                    if message.from_user and message.from_user.username
                    else "гость"
                )
                admin_text = (
                    f"🆕 *Новое обращение #{ticket.id}* (Гость)\n\n"
                    f"От: @{username} (`{telegram_id}`)\n"
                    f"Текст: {message.text}"
                )

            for admin_id in settings.get_admin_ids():
                try:
                    await bot_instance.send_message(
                        admin_id, admin_text, parse_mode="Markdown"
                    )
                except Exception:
                    pass

    except Exception as e:
        await state.clear()
        await message.answer(f"❌ Ошибка создания обращения: {e}")


@router.message(F.text == "📋 Мои обращения")
async def handle_my_tickets(
    message: Message,
    **data: Any,
) -> None:
    """
    Show user's or guest's tickets.
    Uses session_factory for short read transaction.
    Supports both registered users and guests.
    """
    user: User | None = data.get("user")
    telegram_id = message.from_user.id if message.from_user else None
    from app.services.support_service import SupportService

    if not telegram_id:
        await message.answer(
            "❌ Системная ошибка. Отправьте /start или попробуйте позже.",
            reply_markup=support_keyboard(),
        )
        return

    session_factory = data.get("session_factory")

    if not session_factory:
        # Fallback to old session
        session = data.get("session")
        if not session:
            await message.answer(
                "❌ Системная ошибка. Отправьте /start или попробуйте позже.",
                reply_markup=support_keyboard(),
            )
            return
        support_service = SupportService(session)
        if user:
            tickets = await support_service.get_user_tickets(user.id)
        else:
            # Guest tickets
            tickets = await support_service.get_guest_tickets(telegram_id)
    else:
        # NEW pattern: short read transaction
        async with session_factory() as session:
            async with session.begin():
                support_service = SupportService(session)
                if user:
                    tickets = await support_service.get_user_tickets(user.id)
                else:
                    # Guest tickets
                    tickets = await support_service.get_guest_tickets(telegram_id)
        # Transaction closed here

    # R1-8: Просмотр обращений у гостя
    if not tickets:
        if user is None:
            text = (
                "📋 *Мои обращения*\n\n"
                "У вас пока нет обращений.\n\n"
                "Для создания обращения используйте кнопку '✉️ Создать обращение'."
            )
        else:
            text = "📋 У вас пока нет обращений"
    else:
        text = "📋 *Ваши обращения:*\n\n"

        for ticket in tickets[:10]:  # Show last 10
            status_emoji = {
                "open": "🔵",
                "in_progress": "🟡",
                "answered": "🟢",
                "closed": "⚫",
            }.get(ticket.status, "⚪")

            created_date = ticket.created_at.strftime('%d.%m.%Y %H:%M')
            subject = getattr(ticket, 'subject', 'Обращение')
            # Add "(Гость)" marker for guest tickets
            guest_marker = " (Гость)" if user is None else ""
            text += (
                f"{status_emoji} #{ticket.id} - {subject}{guest_marker}\n"
                f"   Создано: {created_date}\n\n"
            )

    await message.answer(
        text, parse_mode="Markdown", reply_markup=support_keyboard()
    )


@router.message(F.text == "❓ FAQ")
async def handle_faq(
    message: Message,
) -> None:
    """Show FAQ."""
    text = (
        "❓ *Часто задаваемые вопросы*\n\n"
        "*Q: Как сделать депозит?*\n"
        "A: Выберите '💰 Депозит' → Выберите уровень → Отправьте USDT.\n"
        "⚠️ **Важно:** Только с личного кошелька (не с биржи)!\n\n"
        "*Q: Как вывести средства?*\n"
        "A: Выберите '💸 Вывод' → Укажите сумму → Подтвердите фин. паролем.\n"
        "ℹ️ Мин. вывод: 0.20 USDT.\n\n"
        "*Q: Как работает реферальная программа?*\n"
        "A: Пригласите друга → Получайте % от его депозитов (до 3 уровней).\n\n"
        "*Q: Что делать если забыл финансовый пароль?*\n"
        "A: Используйте пункт '🔑 Восстановить финпароль'.\n\n"
        "Для других вопросов создайте обращение в поддержку."
    )

    await message.answer(
        text, parse_mode="Markdown", reply_markup=support_keyboard()
    )
