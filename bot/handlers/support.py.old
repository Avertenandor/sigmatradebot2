"""
User Support Handler
Handles user support ticket interactions with multimedia support (PART5)
"""

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SupportCategory, SupportStatus, SupportTicketStatus
from app.services.support_service import SupportService
from app.services.notification_service import NotificationService
from bot.states.support_states import SupportStates
from bot.keyboards.inline import main_menu_keyboard


router = Router(name="support")


def get_category_name(category: SupportCategory) -> str:
    """Get human-readable category name"""
    category_names = {
        SupportCategory.PAYMENTS: "💰 Платежи",
        SupportCategory.WITHDRAWALS: "💸 Выводы",
        SupportCategory.FINPASS: "🔑 Финпароль",
        SupportCategory.REFERRALS: "🤝 Рефералы",
        SupportCategory.TECH: "⚙️ Технический вопрос",
        SupportCategory.OTHER: "❓ Другое",
    }
    return category_names.get(category, str(category))


def get_status_name(status: SupportStatus) -> str:
    """Get human-readable status name"""
    status_names = {
        SupportStatus.OPEN: "🔵 Открыто",
        SupportStatus.IN_PROGRESS: "🟡 В работе",
        SupportStatus.ANSWERED: "🟢 Отвечено",
        SupportStatus.CLOSED: "⚫ Закрыто",
    }
    return status_names.get(status, str(status))


@router.message(F.text == "✉️ Создать обращение")
@router.callback_query(F.data == "support:create")
@router.callback_query(F.data == "support")
async def handle_support_create(
    event: Message | CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user_id: int,
) -> None:
    """Show support menu with category selection"""
    support_service = SupportService(session)

    # Check if user already has an active ticket
    active_ticket = await support_service.get_user_active_ticket(user_id)

    if active_ticket:
        category_enum = SupportCategory(active_ticket.category) if isinstance(active_ticket.category, str) else active_ticket.category
        status_enum = SupportTicketStatus(active_ticket.status) if isinstance(active_ticket.status, str) else active_ticket.status
        message = (
            f"📝 У вас уже есть активное обращение #{active_ticket.id}\n\n"
            f"Категория: {get_category_name(category_enum)}\n"
            f"Статус: {get_status_name(status_enum)}\n\n"
            "Пожалуйста, дождитесь ответа администратора или закрытия "
            "обращения."
        )
        if isinstance(event, Message):
            from bot.keyboards.reply import support_keyboard
            await event.answer(message, reply_markup=support_keyboard())
        else:
            await event.message.edit_text(
                message, reply_markup=main_menu_keyboard()
            )
            await event.answer()
        return

    # Show category selection
    buttons = [
        [
            InlineKeyboardButton(
                text="💰 Платежи", callback_data="support_cat_payments"
            ),
            InlineKeyboardButton(
                text="💸 Выводы", callback_data="support_cat_withdrawals"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔑 Финпароль", callback_data="support_cat_finpass"
            ),
            InlineKeyboardButton(
                text="🤝 Рефералы", callback_data="support_cat_referrals"
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚙️ Тех. вопрос", callback_data="support_cat_tech"
            ),
            InlineKeyboardButton(
                text="❓ Другое", callback_data="support_cat_other"
            ),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    text = "🆘 Техподдержка\n\nВыберите категорию вашего обращения:"
    
    if isinstance(event, Message):
        from bot.keyboards.reply import support_keyboard
        await event.answer(
            text + "\n\nВыберите категорию:",
            reply_markup=keyboard
        )
    else:
        await event.message.edit_text(
            text,
            reply_markup=keyboard,
        )
        await event.answer()


@router.callback_query(F.data.startswith("support_cat_"))
async def handle_support_choose_category(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user_id: int,
) -> None:
    """Handle support category selection"""
    category_map = {
        "support_cat_payments": SupportCategory.PAYMENTS,
        "support_cat_withdrawals": SupportCategory.WITHDRAWALS,
        "support_cat_finpass": SupportCategory.FINPASS,
        "support_cat_referrals": SupportCategory.REFERRALS,
        "support_cat_tech": SupportCategory.TECH,
        "support_cat_other": SupportCategory.OTHER,
    }

    category = category_map.get(callback.data)
    if not category:
        await callback.answer("Неверная категория")
        return

    # Store category in FSM state
    await state.update_data(
        support_category=category.value, support_messages=[]
    )
    await state.set_state(SupportStates.awaiting_input)

    buttons = [
        [InlineKeyboardButton(text="📤 Отправить",
                              callback_data="support_submit")],
        [InlineKeyboardButton(text="❌ Отмена",
                              callback_data="main_menu")],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    message = (
        f"📝 Обращение: {get_category_name(category)}\n\n"
        "Опишите вашу проблему. Вы можете отправить:\n"
        "• Текстовое сообщение\n"
        "• Фото\n"
        "• Голосовое сообщение\n"
        "• Аудио\n"
        "• Документ\n\n"
        'После того как вы добавите все необходимое, нажмите "📤 Отправить".'
    )

    await callback.message.edit_text(message, reply_markup=keyboard)
    await callback.answer()


@router.message(SupportStates.awaiting_input)
async def capture_support_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user_id: int,
) -> None:
    """
    Capture support input (text, photo, voice, audio, document)
    PART5 CRITICAL: Multimedia support
    """
    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button
    if message.text and is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this
    
    data = await state.get_data()
    support_messages = data.get("support_messages", [])

    buttons = [
        [InlineKeyboardButton(text="📤 Отправить",
                              callback_data="support_submit")],
        [InlineKeyboardButton(text="❌ Отмена",
                              callback_data="main_menu")],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    # Handle text
    if message.text and not message.text.startswith("/"):
        support_messages.append({"type": "text", "text": message.text})

        await message.reply(
            "✅ Сообщение добавлено.\n\n"
            "Вы можете добавить ещё информации или нажать "
            '"📤 Отправить" для отправки обращения.',
            reply_markup=keyboard,
        )

    # Handle photo
    elif message.photo:
        photo = message.photo[-1]  # Largest size
        support_messages.append(
            {
                "type": "photo",
                "file_id": photo.file_id,
                "caption": message.caption,
            }
        )

        await message.reply(
            "✅ Фото добавлено.\n\n"
            "Вы можете добавить ещё информации или нажать "
            '"📤 Отправить".',
            reply_markup=keyboard,
        )

    # Handle voice
    elif message.voice:
        support_messages.append(
            {"type": "voice", "file_id": message.voice.file_id}
        )

        await message.reply(
            "✅ Голосовое сообщение добавлено.\n\n"
            "Вы можете добавить ещё информации или нажать "
            '"📤 Отправить".',
            reply_markup=keyboard,
        )

    # Handle audio
    elif message.audio:
        support_messages.append(
            {
                "type": "audio",
                "file_id": message.audio.file_id,
                "caption": message.caption,
            }
        )

        await message.reply(
            "✅ Аудио добавлено.\n\n"
            "Вы можете добавить ещё информации или нажать "
            '"📤 Отправить".',
            reply_markup=keyboard,
        )

    # Handle document
    elif message.document:
        support_messages.append(
            {
                "type": "document",
                "file_id": message.document.file_id,
                "caption": message.caption,
            }
        )

        await message.reply(
            "✅ Документ добавлен.\n\n"
            "Вы можете добавить ещё информации или нажать "
            '"📤 Отправить".',
            reply_markup=keyboard,
        )

    # Update state with messages
    await state.update_data(support_messages=support_messages)


@router.callback_query(
    F.data == "support_submit", SupportStates.awaiting_input
)
async def handle_support_submit(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user_id: int,
) -> None:
    """Submit support ticket"""
    support_service = SupportService(session)
    notification_service = NotificationService(session)

    data = await state.get_data()
    support_category = data.get("support_category")
    support_messages = data.get("support_messages", [])

    if not support_category or not support_messages:
        await callback.answer(
            "❌ Пожалуйста, опишите вашу проблему перед отправкой."
        )
        return

    try:
        # Combine all text messages into one
        text_messages = [
            msg["text"]
            for msg in support_messages
            if msg["type"] == "text"
        ]
        combined_text = "\n\n".join(text_messages) if text_messages else None

        # Collect all attachments
        attachments = [
            {
                "type": msg["type"],
                "file_id": msg["file_id"],
                "caption": msg.get("caption"),
            }
            for msg in support_messages
            if msg["type"] != "text"
        ]

        # Create category enum
        category_enum = SupportCategory(support_category)

        # Create ticket
        ticket = await support_service.create_ticket(
            user_id=user_id,
            category=category_enum,
            initial_message=combined_text,
            attachments=attachments if attachments else None,
        )

        # Clear state
        await state.clear()

        # Notify user
        category_enum = SupportCategory(ticket.category) if isinstance(ticket.category, str) else ticket.category
        message = (
            f"✅ Ваше обращение #{ticket.id} успешно создано!\n\n"
            f"Категория: {get_category_name(category_enum)}\n\n"
            "Администратор ответит вам в ближайшее время. "
            "Вы получите уведомление, когда придёт ответ."
        )

        await callback.message.edit_text(
            message, reply_markup=main_menu_keyboard()
        )
        await callback.answer()

        # Notify admins (handled by service layer)
        await notification_service.notify_admins_new_ticket(callback.bot, ticket.id)

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при создании обращения: {str(e)}",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()


@router.message(F.text == "📋 Мои обращения")
@router.callback_query(F.data == "support:list")
async def handle_support_list(
    event: Message | CallbackQuery,
    session: AsyncSession,
    user_id: int,
) -> None:
    """Show user's support tickets"""
    support_service = SupportService(session)
    
    tickets = await support_service.get_user_tickets(user_id, limit=10)
    
    if not tickets:
        text = "📋 У вас пока нет обращений.\n\nСоздайте новое обращение, если у вас есть вопросы."
    else:
        text = "📋 Ваши обращения:\n\n"
        for ticket in tickets:
            status_emoji = {
                "open": "🔵",
                "in_progress": "🟡",
                "answered": "🟢",
                "closed": "⚫",
            }.get(ticket.status, "❓")
            
            text += (
                f"{status_emoji} #{ticket.id} - {get_category_name(ticket.category)}\n"
                f"   Статус: {get_status_name(ticket.status)}\n"
                f"   Дата: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
    
    if isinstance(event, Message):
        from bot.keyboards.reply import support_keyboard
        await event.answer(text, reply_markup=support_keyboard())
    else:
        await event.message.edit_text(
            text, reply_markup=main_menu_keyboard()
        )
        await event.answer()


@router.message(F.text == "❓ FAQ")
@router.callback_query(F.data == "support:faq")
async def handle_support_faq(
    event: Message | CallbackQuery,
) -> None:
    """Show FAQ with comprehensive information from TZ"""
    text = (
        "❓ **Часто задаваемые вопросы**\n\n"
        "**📌 Что такое SigmaTrade?**\n"
        "SigmaTrade — это платформа для инвестиций в USDT на сети "
        "Binance Smart Chain (BEP-20). Бот позволяет управлять депозитами, "
        "отслеживать начисления и участвовать в партнерской программе.\n\n"
        "🌐 **Официальный сайт:**\n"
        "[sigmatrade.org](https://sigmatrade.org/index.html#exchange)\n\n"
        "**📌 Как создать депозит?**\n"
        "1. Выберите '💰 Депозит' в главном меню\n"
        "2. Выберите доступный уровень депозита (10/50/100/150/300 USDT)\n"
        "3. Отправьте USDT на указанный адрес в сети BSC (BEP-20)\n"
        "4. Введите hash транзакции\n"
        "5. Депозит будет активирован после подтверждения (обычно 1-3 минуты)\n\n"
        "**📌 Правила покупки депозитов:**\n"
        "• Депозиты можно покупать только по возрастающей (1→2→3→4→5)\n"
        "• Нельзя пропустить уровень (например, купить уровень 3 без уровня 2)\n"
        "• Для уровней 2+ требуется наличие активных партнеров уровня 1\n"
        "• Уровень 1 (10 USDT) можно купить без партнеров\n\n"
        "**📌 Как работает партнерская программа?**\n"
        "• Приглашайте друзей по вашей реферальной ссылке\n"
        "• Новый пользователь автоматически становится вашим партнером уровня L1\n"
        "• Вы получаете вознаграждения за активность ваших партнеров\n"
        "• Партнеры влияют на возможность покупки более высоких уровней депозитов\n"
        "• Статистику можно посмотреть в разделе '👥 Рефералы'\n\n"
        "**📌 Как вывести средства?**\n"
        "1. Пройдите верификацию (кнопка '✅ Пройти верификацию')\n"
        "2. Выберите '💸 Вывод' в главном меню\n"
        "3. Укажите сумму (минимум 5 USDT) или выберите 'Вывести все'\n"
        "4. Введите финансовый пароль для подтверждения\n"
        "5. Заявка будет обработана в течение 1-24 часов\n\n"
        "**📌 Как восстановить финансовый пароль?**\n"
        "Обратитесь в поддержку, выбрав категорию '🔑 Финпароль'. "
        "Администратор поможет восстановить доступ.\n\n"
        "**📌 Риски и ограничения:**\n"
        "• Работа ведется только с сетью BSC (BEP-20)\n"
        "• Базовая валюта — USDT BEP-20\n"
        "• Для уровня 1 действует ROI cap 500% (максимум 5x от депозита)\n"
        "• Вывод средств доступен только после верификации\n"
        "• Все транзакции отслеживаются в блокчейне\n\n"
        "**📌 Дополнительная информация:**\n"
        "Подробную информацию о платформе, условиях и правилах можно найти на "
        "[официальном сайте](https://sigmatrade.org/index.html#exchange).\n\n"
        "Если у вас остались вопросы, создайте обращение в поддержку!"
    )
    
    if isinstance(event, Message):
        from bot.keyboards.reply import support_keyboard
        await event.answer(text, reply_markup=support_keyboard(), parse_mode="Markdown")
    else:
        await event.message.edit_text(
            text, reply_markup=main_menu_keyboard(), parse_mode="Markdown"
        )
        await event.answer()
