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
)
from bot.states.admin_states import AdminStates
from bot.utils.menu_buttons import is_menu_button

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
        await state.clear()
        await message.answer(
            "❌ Рассылка отменена.",
            reply_markup=admin_keyboard(),
        )
        return

    # Check if message is a menu button - if so, clear state and ignore
    if message.text and is_menu_button(message.text):
        await state.clear()
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
        await state.clear()
        await message.answer(
            "❌ Рассылка отменена.",
            reply_markup=admin_keyboard(),
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
        await state.clear()
        await message.answer(
            "❌ Рассылка отменена.",
            reply_markup=admin_keyboard(),
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
        await state.clear()
        return

    user_service = UserService(session)
    await message.reply("📨 Ставлю рассылку в очередь...")

    # Get all user telegram IDs
    user_telegram_ids = await user_service.get_all_telegram_ids()

    if not user_telegram_ids:
        await message.reply("❌ Нет пользователей для рассылки")
        await state.clear()
        return

    # Prepare markup if button exists
    reply_markup = None
    if button_data:
        builder = InlineKeyboardBuilder()
        builder.button(text=button_data["text"], url=button_data["url"])
        reply_markup = builder.as_markup()

    # Generate unique broadcast ID
    broadcast_id = f"broadcast_{admin_id}_{int(datetime.now().timestamp())}"

    # Start broadcast (with rate limiting: 15 msg/sec)
    total_users = len(user_telegram_ids)
    success_count = 0
    failed_count = 0

    await message.reply(
        f"✅ Рассылка запущена!\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"⏱ Примерное время: {int(total_users / 15) + 1} сек.\n"
        f"🔗 Кнопка: {'✅ ' + button_data['text'] if button_data else '❌ Нет'}\n\n"
        f"📊 Рассылка идёт в фоновом режиме с ограничением 15 сообщений/сек.\n"
        f"✉️ ID рассылки: `{broadcast_id}`",
        parse_mode="Markdown",
    )

    broadcast_type = broadcast_data["type"]
    text = broadcast_data.get("text")
    file_id = broadcast_data.get("file_id")
    caption = broadcast_data.get("caption")

    # Send messages with rate limiting
    for i, telegram_id in enumerate(user_telegram_ids):
        try:
            if broadcast_type == "text":
                await message.bot.send_message(
                    telegram_id,
                    text,
                    parse_mode="Markdown",
                    reply_markup=reply_markup,
                )
            elif broadcast_type == "photo":
                await message.bot.send_photo(
                    telegram_id,
                    file_id,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                    reply_markup=reply_markup,
                )
            elif broadcast_type == "voice":
                await message.bot.send_voice(
                    telegram_id,
                    file_id,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                    reply_markup=reply_markup,
                )
            elif broadcast_type == "audio":
                await message.bot.send_audio(
                    telegram_id,
                    file_id,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                    reply_markup=reply_markup,
                )

            success_count += 1

            # Rate limiting: 15 messages per second
            if (i + 1) % 15 == 0:
                await asyncio.sleep(1)

        except Exception:
            failed_count += 1
            continue

    # Record broadcast timestamp for rate limiting
    broadcast_rate_limits[admin_id] = datetime.now()

    # Send completion message
    await message.reply(
        f"✅ **Рассылка завершена!**\n\n"
        f"✅ Успешно: {success_count}\n"
        f"❌ Ошибки: {failed_count}\n"
        f"👥 Всего: {total_users}\n"
        f"🔗 С кнопкой: {'Да' if button_data else 'Нет'}",
        parse_mode="Markdown",
        reply_markup=admin_keyboard(),
    )

    # Log admin action
    admin: Admin | None = data.get("admin")
    if admin:
        log_service = AdminLogService(session)
        message_preview = text or caption or f"{broadcast_type} message"
        if button_data:
            message_preview += f" [Button: {button_data['text']}]"
            
        await log_service.log_broadcast_sent(
            admin=admin,
            total_users=success_count,
            message_preview=message_preview,
        )

    # Reset state
    await state.clear()
