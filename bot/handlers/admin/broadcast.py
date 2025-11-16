"""
Admin Broadcast Handler
Handles broadcasting messages with multimedia support (PART5 CRITICAL)
Supports: text, photo, voice, audio
"""

import asyncio
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService
from bot.states.admin_states import AdminStates

router = Router(name="admin_broadcast")

# Rate limiting for broadcasts (15 minutes cooldown)
broadcast_rate_limits: dict[int, datetime] = {}
BROADCAST_COOLDOWN_MS = 15 * 60 * 1000  # 15 minutes in milliseconds


def get_cancel_button() -> InlineKeyboardMarkup:
    """Get cancel button keyboard"""
    buttons = [
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "admin_broadcast")
async def handle_start_broadcast(
    callback: CallbackQuery,
    state: FSMContext,
    is_admin: bool = False,
    admin_id: int = 0,
) -> None:
    """
    Start broadcast message
    PART5 CRITICAL: Multimedia broadcast support
    """
    if not is_admin:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return

    # Check rate limit
    now = datetime.now()
    last_broadcast = broadcast_rate_limits.get(admin_id)

    if last_broadcast:
        time_since_last = (now - last_broadcast).total_seconds() * 1000
        remaining_cooldown = BROADCAST_COOLDOWN_MS - time_since_last

        if remaining_cooldown > 0:
            remaining_minutes = int(remaining_cooldown / 60000) + 1
            await callback.answer(
                f"⏳ Подождите {remaining_minutes} мин. перед следующей "
                "рассылкой",
                show_alert=True,
            )
            return

    await state.set_state(AdminStates.awaiting_broadcast_message)

    message = """
📢 **Рассылка всем пользователям**

Отправьте сообщение, которое хотите разослать всем пользователям бота.

⚠️ Сообщение получат все зарегистрированные пользователи.
⚙️ Рассылка использует ограничение **15 сообщений/сек**.

**Поддерживается:**
• **Текст** — Просто отправьте текстовое сообщение (поддерживается Markdown)
• **Фото** — Прикрепите фото и добавьте текст в caption
• **Голосовые** — Отправьте голосовое сообщение (caption опционален)
• **Аудио** — Отправьте аудиофайл (caption опционален)

**Примеры:**
📝 Текст: "Привет! **Новая акция** до конца недели!"
🖼 Фото: Прикрепите фото + caption "Новые продукты в наличии"
🎙 Голосовое: Запишите аудиосообщение для пользователей
🎵 Аудио: Отправьте музыкальный файл + описание
    """.strip()

    await callback.message.edit_text(
        message, parse_mode="Markdown", reply_markup=get_cancel_button()
    )
    await callback.answer()


@router.message(AdminStates.awaiting_broadcast_message)
async def handle_broadcast_message(  # noqa: C901
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    is_admin: bool = False,
    admin_id: int = 0,
) -> None:
    """
    Handle broadcast message input
    PART5 CRITICAL: Supports text, photo, voice, audio
    """
    if not is_admin:
        return

    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if message.text and is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this

    user_service = UserService(session)

    # Determine message type
    broadcast_type = "text"
    file_id = None
    caption = None
    text = None

    if message.text:
        broadcast_type = "text"
        text = message.text
    elif message.photo:
        broadcast_type = "photo"
        file_id = message.photo[-1].file_id  # Largest size
        caption = message.caption
    elif message.voice:
        broadcast_type = "voice"
        file_id = message.voice.file_id
        caption = message.caption
    elif message.audio:
        broadcast_type = "audio"
        file_id = message.audio.file_id
        caption = message.caption
    else:
        await message.reply(
            "❌ Неподдерживаемый тип сообщения. "
            "Используйте текст, фото, голосовое или аудио."
        )
        return

    await message.reply("📨 Ставлю рассылку в очередь...")

    # Get all user telegram IDs
    user_telegram_ids = await user_service.get_all_telegram_ids()

    if not user_telegram_ids:
        await message.reply("❌ Нет пользователей для рассылки")
        await state.clear()
        return

    # Generate unique broadcast ID
    broadcast_id = f"broadcast_{admin_id}_{int(datetime.now().timestamp())}"

    # Start broadcast (with rate limiting: 15 msg/sec)
    total_users = len(user_telegram_ids)
    success_count = 0
    failed_count = 0

    await message.reply(
        f"✅ Рассылка запущена!\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"⏱ Примерное время: {int(total_users / 15) + 1} сек.\n\n"
        f"📊 Рассылка идёт в фоновом режиме с ограничением 15 сообщений/сек.\n"
        f"✉️ ID рассылки: `{broadcast_id}`",
        parse_mode="Markdown",
    )

    # Send messages with rate limiting
    for i, telegram_id in enumerate(user_telegram_ids):
        try:
            if broadcast_type == "text":
                await message.bot.send_message(
                    telegram_id, text, parse_mode="Markdown"
                )
            elif broadcast_type == "photo":
                await message.bot.send_photo(
                    telegram_id,
                    file_id,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                )
            elif broadcast_type == "voice":
                await message.bot.send_voice(
                    telegram_id,
                    file_id,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                )
            elif broadcast_type == "audio":
                await message.bot.send_audio(
                    telegram_id,
                    file_id,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
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
        f"👥 Всего: {total_users}",
        parse_mode="Markdown",
    )

    # Reset state
    await state.clear()
