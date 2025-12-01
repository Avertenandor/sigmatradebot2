"""
Admin Broadcast Handler
Handles broadcasting messages with multimedia support and link buttons (PART5 CRITICAL)
Supports: text, photo, voice, audio + inline link buttons
"""

import asyncio
from datetime import datetime
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.services.admin_log_service import AdminLogService
from app.services.user_service import UserService
from bot.keyboards.reply import (
    admin_broadcast_button_choice_keyboard,
    admin_broadcast_cancel_keyboard,
    admin_broadcast_keyboard,
    admin_keyboard,
    get_admin_keyboard_from_data,
)
from bot.states.admin_states import AdminStates
from bot.utils.menu_buttons import is_menu_button
from bot.utils.admin_utils import clear_state_preserve_admin_token

router = Router(name="admin_broadcast")

# Rate limiting for broadcasts (1 minute cooldown)
broadcast_rate_limits: dict[int, datetime] = {}
BROADCAST_COOLDOWN_MS = 1 * 60 * 1000  # 1 minute in milliseconds


@router.message(F.text == "📢 Рассылка")
async def handle_start_broadcast(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Start broadcast message
    PART5 CRITICAL: Multimedia broadcast support
    """
    is_admin = data.get("is_admin", False)
    admin_id = data.get("admin_id", 0)

    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    # Check rate limit
    now = datetime.now()
    last_broadcast = broadcast_rate_limits.get(admin_id)

    if last_broadcast:
        time_since_last = (now - last_broadcast).total_seconds() * 1000
        remaining_cooldown = BROADCAST_COOLDOWN_MS - time_since_last

        if remaining_cooldown > 0:
            remaining_minutes = int(remaining_cooldown / 60000) + 1
            await message.answer(
                f"⏳ Подождите {remaining_minutes} мин. перед следующей рассылкой",
                reply_markup=admin_broadcast_keyboard(),
            )
            return

    await state.set_state(AdminStates.awaiting_broadcast_message)

    text = """
📢 **Рассылка всем пользователям**

Отправьте сообщение, которое хотите разослать всем пользователям бота.

⚠️ Сообщение получат все зарегистрированные пользователи.
⚙️ Рассылка использует ограничение **15 сообщений/сек**.

**Поддерживается:**
• **Текст** — Просто отправьте текстовое сообщение (поддерживается Markdown)
• **Фото** — Прикрепите фото и добавьте текст в caption
• **Голосовые** — Отправьте голосовое сообщение (caption опционален)
• **Аудио** — Отправьте аудиофайл (caption опционален)

**Теперь можно добавить кнопку-ссылку!**
После отправки сообщения бот предложит добавить кнопку с ссылкой на сайт или канал.
    """.strip()

    await message.answer(
        text, parse_mode="Markdown", reply_markup=admin_broadcast_keyboard()
    )


@router.message(AdminStates.awaiting_broadcast_message)
async def handle_broadcast_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Handle broadcast message input and ask about button.
    """
    is_admin = data.get("is_admin", False)

    if not is_admin:
        return

    # Check if message is a cancel button
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "❌ Рассылка отменена.",
            reply_markup=get_admin_keyboard_from_data(data),
        )
        return

    # Check if message is a menu button - if so, clear state and ignore
    if message.text and is_menu_button(message.text):
        await clear_state_preserve_admin_token(state)
        return  # Let menu handlers process this

    # Determine message type and save to state
    broadcast_data = {}

    if message.text:
        broadcast_data["type"] = "text"
        broadcast_data["text"] = message.text
    elif message.photo:
        broadcast_data["type"] = "photo"
        broadcast_data["file_id"] = message.photo[-1].file_id  # Largest size
        broadcast_data["caption"] = message.caption
    elif message.voice:
        broadcast_data["type"] = "voice"
        broadcast_data["file_id"] = message.voice.file_id
        broadcast_data["caption"] = message.caption
    elif message.audio:
        broadcast_data["type"] = "audio"
        broadcast_data["file_id"] = message.audio.file_id
        broadcast_data["caption"] = message.caption
    else:
        await message.reply(
            "❌ Неподдерживаемый тип сообщения. "
            "Используйте текст, фото, голосовое или аудио."
        )
        return

    await state.update_data(broadcast_data=broadcast_data)
    await state.set_state(AdminStates.awaiting_broadcast_button_choice)

    await message.reply(
        "📝 **Сообщение получено!**\n\n"
        "Хотите добавить к сообщению кнопку с ссылкой?\n"
        "Это удобно для перенаправления на сайт или канал.",
        reply_markup=admin_broadcast_button_choice_keyboard(),
        parse_mode="Markdown",
    )


@router.message(AdminStates.awaiting_broadcast_button_choice)
async def handle_button_choice(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle button choice (add or skip)."""
    if message.text == "✅ Добавить кнопку":
        await state.set_state(AdminStates.awaiting_broadcast_button_link)
        await message.reply(
            "🔗 **Введите текст кнопки и ссылку**\n\n"
            "Формат: `Текст кнопки | https://ссылка.com`\n\n"
            "Пример: `Наш сайт | https://google.com`\n"
            "Пример 2: `Канал новостей | https://t.me/durov`",
            parse_mode="Markdown",
            reply_markup=admin_broadcast_cancel_keyboard(),
        )

    elif message.text == "🚀 Отправить без кнопки":
        # Proceed without button
        await execute_broadcast(message, state, session, **data)

    elif message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "❌ Рассылка отменена.",
            reply_markup=get_admin_keyboard_from_data(data),
        )

    else:
        await message.reply(
            "Пожалуйста, выберите действие на клавиатуре.",
            reply_markup=admin_broadcast_button_choice_keyboard(),
        )


@router.message(AdminStates.awaiting_broadcast_button_link)
async def handle_button_link(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle button link input."""
    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "❌ Рассылка отменена.",
            reply_markup=get_admin_keyboard_from_data(data),
        )
        return

    text = message.text.strip()
    if "|" not in text:
        await message.reply(
            "❌ Неверный формат! Используйте разделитель `|`\n\n"
            "Пример: `Перейти на сайт | https://google.com`",
            parse_mode="Markdown",
        )
        return

    button_text, url = text.split("|", 1)
    button_text = button_text.strip()
    url = url.strip()

    if not url.startswith("http") and not url.startswith("t.me"):
        await message.reply(
            "❌ Ссылка должна начинаться с `http://`, `https://` или `t.me`",
            parse_mode="Markdown",
        )
        return

    # Save button data
    await state.update_data(button={"text": button_text, "url": url})
    
    # Execute broadcast with button
    await execute_broadcast(message, state, session, **data)


async def execute_broadcast(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Execute the broadcast."""
    is_admin = data.get("is_admin", False)
    admin_id = data.get("admin_id", 0)

    state_data = await state.get_data()
    broadcast_data = state_data.get("broadcast_data")
    button_data = state_data.get("button")

    if not broadcast_data:
        await message.reply("❌ Ошибка: данные рассылки потеряны")
        await clear_state_preserve_admin_token(state)
        return

    from app.services.broadcast_service import BroadcastService
    
    # Start broadcast in background
    service = BroadcastService(session, message.bot)
    broadcast_id = await service.start_broadcast(
        admin_id=admin_id,
        broadcast_data=broadcast_data,
        button_data=button_data,
        admin_telegram_id=message.chat.id
    )

    # Record broadcast timestamp for rate limiting
    broadcast_rate_limits[admin_id] = datetime.now()

    await message.reply(
        f"✅ **Рассылка запущена в фоне!**\n\n"
        f"✉️ ID: `{broadcast_id}`\n"
        f"Вы получите уведомление по завершении.",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard_from_data(data),
    )

    # Log admin action (start)
    admin: Admin | None = data.get("admin")
    if admin:
        log_service = AdminLogService(session)
        message_preview = broadcast_data.get("text") or broadcast_data.get("caption") or f"{broadcast_data['type']} message"
        if button_data:
            message_preview += f" [Button: {button_data['text']}]"
            
        await log_service.log_broadcast_sent(
            admin=admin,
            total_users=0, # Unknown at start
            message_preview=f"Started: {message_preview}",
        )

    # Reset state
    await clear_state_preserve_admin_token(state)
