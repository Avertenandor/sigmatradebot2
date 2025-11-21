"""
Language selection handler.

R13-3: Handles language change for users.
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from bot.i18n import get_translator, set_user_language, get_user_language, SUPPORTED_LANGUAGES
from bot.keyboards.reply import settings_keyboard

router = Router(name="language")


@router.message(F.text == "🌐 Изменить язык")
@router.message(F.text == "🌐 Change Language")
async def handle_language_menu(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show language selection menu."""
    await state.clear()

    # Get current language
    current_lang = await get_user_language(session, user.id)
    t = get_translator(current_lang)

    # Create language selection keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇬🇧 English")],
            [KeyboardButton(text=t("common.back"))],
        ],
        resize_keyboard=True,
    )

    text = t("language.title")
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.message(F.text.in_(["🇷🇺 Русский", "🇬🇧 English"]))
async def handle_language_selection(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle language selection."""
    await state.clear()

    # Map button text to language code
    language_map = {
        "🇷🇺 Русский": "ru",
        "🇬🇧 English": "en",
    }

    selected_lang = language_map.get(message.text)
    if not selected_lang:
        await message.answer("❌ Неверный выбор языка / Invalid language selection")
        return

    # Set user language
    success = await set_user_language(session, user.id, selected_lang)

    if success:
        # Get translator for new language
        t = get_translator(selected_lang)
        language_name = SUPPORTED_LANGUAGES[selected_lang]

        text = t("language.changed", language=language_name)
        await message.answer(
            text,
            reply_markup=settings_keyboard(),
            parse_mode="Markdown",
        )
        logger.info(f"Language changed to {selected_lang} for user {user.id}")
    else:
        # Get current language for error message
        current_lang = await get_user_language(session, user.id)
        t = get_translator(current_lang)

        text = t("language.error")
        await message.answer(
            text,
            reply_markup=settings_keyboard(),
            parse_mode="Markdown",
        )

