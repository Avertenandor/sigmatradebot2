"""
Contact Update Handler - ТОЛЬКО REPLY KEYBOARDS!

Handles user contact information updates (phone and email).
"""

from typing import Any

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from bot.keyboards.reply import (
    contact_input_keyboard,
    contact_update_menu_keyboard,
    settings_keyboard,
)
from bot.states.profile_update import ProfileUpdateStates

router = Router(name="contact_update")


@router.message(StateFilter('*'), F.text == "📝 Обновить контакты")
async def start_update_contacts(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Start contact update flow with menu.

    Args:
        message: Telegram message
        session: Database session
        state: FSM state
        **data: Handler data
    """
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        return

    await state.clear()

    # Show current contacts
    phone_display = user.phone or "не указан"
    email_display = user.email or "не указан"

    text = (
        f"📝 *Обновление контактов*\n\n"
        f"📋 **Текущие контакты:**\n"
        f"📞 Телефон: `{phone_display}`\n"
        f"📧 Email: `{email_display}`\n\n"
        f"Что вы хотите обновить?"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=contact_update_menu_keyboard(),
    )
    await state.set_state(ProfileUpdateStates.choosing_contact_type)


@router.message(
    ProfileUpdateStates.choosing_contact_type, F.text == "◀️ Назад"
)
async def back_from_choice(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Go back from contact choice to settings."""
    await state.clear()
    
    # Check for language
    from bot.i18n.loader import get_user_language
    user: User | None = data.get("user")
    language = "ru"
    if user:
        language = await get_user_language(session, user.id)
        
    await message.answer(
        "⚙️ *Настройки*\n\nВыберите раздел:",
        parse_mode="Markdown",
        reply_markup=settings_keyboard(language),
    )


@router.message(
    ProfileUpdateStates.choosing_contact_type, F.text == "🏠 Главное меню"
)
async def home_from_choice(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Go to main menu from choice."""
    user: User | None = data.get("user")
    if not user:
        await state.clear()
        return

    await state.clear()

    from bot.handlers.menu import show_main_menu

    await show_main_menu(message, session, user, state, **data)


@router.message(
    ProfileUpdateStates.choosing_contact_type, F.text == "📞 Обновить телефон"
)
async def start_phone_update(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start phone update."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    current_phone = user.phone or "не указан"

    text = (
        f"📞 **Обновление телефона**\n\n"
        f"Текущий номер: `{current_phone}`\n\n"
        f"Введите новый номер телефона в формате:\n"
        f"`+79991234567` или `89991234567`\n\n"
        f"Или нажмите кнопку ниже:"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=contact_input_keyboard(),
    )
    await state.set_state(ProfileUpdateStates.waiting_for_phone)


@router.message(
    ProfileUpdateStates.choosing_contact_type, F.text == "📧 Обновить email"
)
async def start_email_update(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start email update."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    current_email = user.email or "не указан"

    text = (
        f"📧 **Обновление email**\n\n"
        f"Текущий email: `{current_email}`\n\n"
        f"Введите новый email адрес в формате:\n"
        f"`example@mail.com`\n\n"
        f"Или нажмите кнопку ниже:"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=contact_input_keyboard(),
    )
    await state.set_state(ProfileUpdateStates.waiting_for_email)


@router.message(
    ProfileUpdateStates.choosing_contact_type, F.text == "📝 Обновить оба"
)
async def start_both_update(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start updating both contacts."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    current_phone = user.phone or "не указан"

    text = (
        f"📞 **Обновление контактов (шаг 1/2)**\n\n"
        f"Текущий телефон: `{current_phone}`\n\n"
        f"Введите новый номер телефона в формате:\n"
        f"`+79991234567` или `89991234567`\n\n"
        f"Или нажмите кнопку ниже:"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=contact_input_keyboard(),
    )
    # Save flag that we're updating both
    await state.update_data(updating_both=True)
    await state.set_state(ProfileUpdateStates.waiting_for_phone)


@router.message(ProfileUpdateStates.waiting_for_phone, F.text == "⏭ Пропустить")
async def skip_phone_update(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Skip phone update."""
    state_data = await state.get_data()
    updating_both = state_data.get("updating_both", False)

    if updating_both:
        # Move to email
        user: User | None = data.get("user")
        current_email = user.email if user else "не указан"

        text = (
            f"📧 **Обновление контактов (шаг 2/2)**\n\n"
            f"Текущий email: `{current_email}`\n\n"
            f"Введите новый email адрес в формате:\n"
            f"`example@mail.com`\n\n"
            f"Или нажмите кнопку ниже:"
        )

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=contact_input_keyboard(),
        )
        await state.set_state(ProfileUpdateStates.waiting_for_email)
    else:
        # Just finish
        await state.clear()
        await message.answer(
            "✅ Телефон оставлен без изменений",
            reply_markup=settings_keyboard(),
        )


@router.message(ProfileUpdateStates.waiting_for_phone, F.text == "◀️ Назад")
async def back_from_phone(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Go back to contact menu."""
    await start_update_contacts(message, session, state, **data)


@router.message(ProfileUpdateStates.waiting_for_phone, F.text == "🏠 Главное меню")
async def home_from_phone(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Go to main menu."""
    user: User | None = data.get("user")
    if not user:
        await state.clear()
        return

    await state.clear()

    from bot.handlers.menu import show_main_menu

    await show_main_menu(message, session, user, state, **data)


@router.message(ProfileUpdateStates.waiting_for_phone)
async def process_phone_update(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Process phone number update.

    Args:
        message: Telegram message
        session: Database session
        state: FSM state
        **data: Handler data
    """
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    phone = message.text.strip() if message.text else None

    if not phone:
        await message.answer("❌ Пожалуйста, введите номер телефона")
        return

    # Basic phone validation
    # Remove spaces and dashes
    phone_clean = (
        phone.replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if len(phone_clean) < 10:
        await message.answer(
            "❌ Номер телефона слишком короткий. Минимум 10 цифр.\n\n"
            "Попробуйте еще раз или нажмите '⏭ Пропустить'"
        )
        return

    # Update phone
    from app.repositories.user_repository import UserRepository

    user_repo = UserRepository(session)
    await user_repo.update(user.id, phone=phone_clean)
    await session.commit()

    # Check if updating both
    state_data = await state.get_data()
    updating_both = state_data.get("updating_both", False)

    if updating_both:
        # Move to email
        current_email = user.email or "не указан"

        text = (
            f"✅ Телефон обновлен: `{phone_clean}`\n\n"
            f"📧 **Обновление контактов (шаг 2/2)**\n\n"
            f"Текущий email: `{current_email}`\n\n"
            f"Введите новый email адрес в формате:\n"
            f"`example@mail.com`\n\n"
            f"Или нажмите кнопку ниже:"
        )

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=contact_input_keyboard(),
        )
        await state.set_state(ProfileUpdateStates.waiting_for_email)
    else:
        # Just finish
        await state.clear()

        text = (
            f"✅ **Телефон успешно обновлен!**\n\n"
            f"📞 Новый номер: `{phone_clean}`\n\n"
            f"💡 Данные сохранены в вашем профиле."
        )

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=settings_keyboard(),
        )


@router.message(ProfileUpdateStates.waiting_for_email, F.text == "⏭ Пропустить")
async def skip_email_update(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Skip email update."""
    await state.clear()
    await message.answer(
        "✅ Email оставлен без изменений",
        reply_markup=settings_keyboard(),
    )


@router.message(ProfileUpdateStates.waiting_for_email, F.text == "◀️ Назад")
async def back_from_email(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Go back to contact menu."""
    await start_update_contacts(message, session, state, **data)


@router.message(ProfileUpdateStates.waiting_for_email, F.text == "🏠 Главное меню")
async def home_from_email(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Go to main menu."""
    user: User | None = data.get("user")
    if not user:
        await state.clear()
        return

    await state.clear()

    from bot.handlers.menu import show_main_menu

    await show_main_menu(message, session, user, state, **data)


@router.message(ProfileUpdateStates.waiting_for_email)
async def process_email_update(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Process email update.

    Args:
        message: Telegram message
        session: Database session
        state: FSM state
        **data: Handler data
    """
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    email = message.text.strip() if message.text else None

    if not email:
        await message.answer("❌ Пожалуйста, введите email адрес")
        return

    # Basic email validation
    if "@" not in email or "." not in email.split("@")[-1]:
        await message.answer(
            "❌ Неверный формат email. Должен содержать @ и домен.\n\n"
            "Пример: `example@mail.com`\n\n"
            "Попробуйте еще раз или нажмите '⏭ Пропустить'",
            parse_mode="Markdown",
        )
        return

    # Update email
    from app.repositories.user_repository import UserRepository

    user_repo = UserRepository(session)
    await user_repo.update(user.id, email=email.lower())
    await session.commit()

    await state.clear()

    # Show final result
    user_updated = await user_repo.get_by_id(user.id)
    phone_display = (
        user_updated.phone
        if user_updated and user_updated.phone
        else "не указан"
    )
    email_display = (
        user_updated.email
        if user_updated and user_updated.email
        else "не указан"
    )

    text = (
        f"✅ **Контакты успешно обновлены!**\n\n"
        f"📋 **Ваши контакты:**\n"
        f"📞 Телефон: `{phone_display}`\n"
        f"📧 Email: `{email_display}`\n\n"
        f"💡 Эти данные сохранены в вашем профиле и доступны администраторам."
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=settings_keyboard(),
    )

