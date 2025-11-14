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

from app.models.enums import SupportCategory, SupportStatus
from app.services.support_service import SupportService
from app.services.notification_service import NotificationService
from bot.states.support_states import SupportStates
from bot.keyboards.main_keyboard import get_main_keyboard


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


@router.callback_query(F.data == "support")
async def handle_support_menu(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user_id: int,
) -> None:
    """Show support menu with category selection"""
    support_service = SupportService(session)

    # Check if user already has an active ticket
    active_ticket = await support_service.get_user_active_ticket(user_id)

    if active_ticket:
        message = (
            f"📝 У вас уже есть активное обращение #{active_ticket.id}\n\n"
            f"Категория: {get_category_name(active_ticket.category)}\n"
            f"Статус: {get_status_name(active_ticket.status)}\n\n"
            "Пожалуйста, дождитесь ответа администратора или закрытия "
            "обращения."
        )
        await callback.message.edit_text(
            message, reply_markup=get_main_keyboard()
        )
        await callback.answer()
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
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "🆘 Техподдержка\n\nВыберите категорию вашего обращения:",
        reply_markup=keyboard,
    )
    await callback.answer()


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
        message = (
            f"✅ Ваше обращение #{ticket.id} успешно создано!\n\n"
            f"Категория: {get_category_name(ticket.category)}\n\n"
            "Администратор ответит вам в ближайшее время. "
            "Вы получите уведомление, когда придёт ответ."
        )

        await callback.message.edit_text(
            message, reply_markup=get_main_keyboard()
        )
        await callback.answer()

        # Notify admins (handled by service layer)
        await notification_service.notify_admins_new_ticket(ticket.id)

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при создании обращения: {str(e)}",
            reply_markup=get_main_keyboard(),
        )
        await callback.answer()
