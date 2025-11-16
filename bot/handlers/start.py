"""
Start handler.

Handles /start command and user registration.
"""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.user_service import UserService
from bot.keyboards.reply import main_menu_reply_keyboard
from bot.states.registration import RegistrationStates

router = Router()


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    session: AsyncSession,
    user: User | None,
    state: FSMContext,
) -> None:
    """
    Handle /start command with referral code support.

    Args:
        message: Telegram message
        session: Database session
        user: Current user (if registered)
        state: FSM state
    """
    # Extract referral code from command args
    # Format: /start ref123456 or /start ref_123456
    referrer_telegram_id = None
    if message.text and len(message.text.split()) > 1:
        ref_arg = message.text.split()[1].strip()
        # Support formats: ref123456, ref_123456, ref-123456
        if ref_arg.startswith("ref"):
            try:
                # Extract telegram_id from ref code
                ref_id_str = (
                    ref_arg.replace("ref", "")
                    .replace("_", "")
                    .replace("-", "")
                )
                if ref_id_str.isdigit():
                    referrer_telegram_id = int(ref_id_str)
                    logger.info(
                        "Referral code detected",
                        extra={
                            "ref_code": ref_arg,
                            "referrer_telegram_id": referrer_telegram_id,
                            "new_user_telegram_id": message.from_user.id,
                        },
                    )
            except (ValueError, AttributeError):
                logger.warning(
                    "Invalid referral code format",
                    extra={"ref_code": ref_arg},
                )

    # Check if already registered
    if user:
        welcome_text = (
            f"Добро пожаловать обратно, {user.username or 'пользователь'}!\n\n"
            f"Ваш баланс: {user.balance} USDT\n"
            f"Используйте меню ниже для навигации."
        )
        await message.answer(
            welcome_text,
            reply_markup=main_menu_reply_keyboard(),
        )
        return

    # Start registration with referral code
    welcome_text = (
        "👋 **Добро пожаловать в SigmaTrade!**\n\n"
        "SigmaTrade — это платформа для инвестиций в USDT на сети "
        "Binance Smart Chain (BEP-20).\n\n"
        "**Важно:**\n"
        "• Работа ведется только с сетью **BSC (BEP-20)**\n"
        "• Базовая валюта депозитов — **USDT BEP-20**\n\n"
        "🌐 **Официальный сайт:**\n"
        "[sigmatrade.org](https://sigmatrade.org/index.html#exchange)\n\n"
        "Для начала работы необходимо пройти регистрацию.\n\n"
        "📝 **Шаг 1:** Введите ваш BSC (BEP-20) адрес кошелька\n"
        "Формат: `0x...` (42 символа)\n\n"
        "❗️ **Внимание:** убедитесь, что адрес указан правильно!"
    )

    if referrer_telegram_id:
        # Save referrer to state for later use
        await state.update_data(referrer_telegram_id=referrer_telegram_id)
        welcome_text += (
            "\n\n✅ Реферальный код принят! "
            "После регистрации вы будете привязаны к пригласившему."
        )

    await message.answer(
        welcome_text,
        parse_mode="Markdown",
        disable_web_page_preview=False,
    )

    await state.set_state(RegistrationStates.waiting_for_wallet)


@router.message(RegistrationStates.waiting_for_wallet)
async def process_wallet(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """
    Process wallet address.

    Args:
        message: Telegram message
        session: Database session
        state: FSM state
    """
    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this

    wallet_address = message.text.strip()

    # Validate wallet format (0x + 40 hex chars)
    if not wallet_address.startswith("0x") or len(wallet_address) != 42:
        await message.answer(
            "❌ Неверный формат адреса!\n\n"
            "BSC адрес должен начинаться с '0x' и содержать 42 символа.\n"
            "Попробуйте еще раз:"
        )
        return

    # Check if wallet already registered
    user_service = UserService(session)
    existing = await user_service.get_by_wallet(wallet_address)

    if existing:
        await message.answer(
            "❌ Этот кошелек уже зарегистрирован!\n\nИспользуйте другой адрес:"
        )
        return

    # Save wallet to state
    await state.update_data(wallet_address=wallet_address)

    # Ask for financial password
    await message.answer(
        "✅ Адрес кошелька принят!\n\n"
        "📝 Шаг 2: Создайте финансовый пароль\n"
        "Этот пароль будет использоваться для подтверждения выводов.\n\n"
        "Требования:\n"
        "• Минимум 6 символов\n"
        "• Не используйте простые пароли\n\n"
        "Введите пароль:"
    )

    await state.set_state(RegistrationStates.waiting_for_financial_password)


@router.message(RegistrationStates.waiting_for_financial_password)
async def process_financial_password(
    message: Message, state: FSMContext
) -> None:
    """
    Process financial password.

    Args:
        message: Telegram message
        state: FSM state
    """
    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this

    password = message.text.strip()

    # Validate password
    if len(password) < 6:
        await message.answer(
            "❌ Пароль слишком короткий!\n\n"
            "Минимальная длина: 6 символов.\n"
            "Попробуйте еще раз:"
        )
        return

    # Delete message with password
    await message.delete()

    # Save password to state
    await state.update_data(financial_password=password)

    # Ask for confirmation
    await message.answer(
        "✅ Пароль принят!\n\n"
        "📝 Шаг 3: Подтвердите пароль\n"
        "Введите пароль еще раз:"
    )

    await state.set_state(RegistrationStates.waiting_for_password_confirmation)


@router.message(RegistrationStates.waiting_for_password_confirmation)
async def process_password_confirmation(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    """
    Process password confirmation and complete registration.

    Args:
        message: Telegram message
        session: Database session
        state: FSM state
    """
    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this

    confirmation = message.text.strip()

    # Delete message with password
    await message.delete()

    # Get data from state
    data = await state.get_data()
    password = data.get("financial_password")

    # Check if passwords match
    if confirmation != password:
        await message.answer(
            "❌ Пароли не совпадают!\n\nВведите пароль еще раз:"
        )
        await state.set_state(
            RegistrationStates.waiting_for_financial_password
        )
        return

    # Register user
    wallet_address = data.get("wallet_address")
    referrer_telegram_id = data.get("referrer_telegram_id")
    user_service = UserService(session)

    try:
        user = await user_service.register_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            wallet_address=wallet_address,
            financial_password=password,
            referrer_telegram_id=referrer_telegram_id,
        )
    except ValueError as e:
        error_msg = str(e)

        # Check if it's a blacklist error
        if error_msg.startswith("BLACKLISTED:"):
            action_type = error_msg.split(":")[1]
            from app.models.blacklist import BlacklistActionType

            if action_type == BlacklistActionType.REGISTRATION_DENIED:
                await message.answer(
                    "Здравствуйте, по решению участников нашего "
                    "сообщества вам отказано в регистрации в нашем "
                    "боте и других инструментах нашего сообщества."
                )
            else:
                # Should not happen during registration, but handle gracefully
                await message.answer(
                    "❌ Ошибка регистрации. Обратитесь в поддержку."
                )
        else:
            await message.answer(
                f"❌ Ошибка регистрации:\n{error_msg}\n\n"
                "Попробуйте начать заново: /start"
            )
        await state.clear()
        return

    # Registration successful
    logger.info(
        "User registered successfully",
        extra={
            "user_id": user.id,
            "telegram_id": message.from_user.id,
        },
    )

    await message.answer(
        "🎉 Регистрация завершена!\n\n"
        f"Ваш ID: {user.id}\n"
        f"Кошелек: {user.masked_wallet}\n\n"
        "Добро пожаловать в SigmaTrade! 🚀",
        reply_markup=main_menu_reply_keyboard(),
    )

    # Ask if user wants to provide contacts (optional)
    contacts_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, оставить контакты",
                    callback_data="registration:add_contacts",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⏭ Пропустить",
                    callback_data="registration:skip_contacts",
                ),
            ],
        ]
    )

    await message.answer(
        "📝 **Опционально:** Вы можете оставить контакты для связи "
        "(телефон и/или email). Это необязательно.\n\n"
        "Хотите оставить контакты?",
        parse_mode="Markdown",
        reply_markup=contacts_keyboard,
    )

    await state.set_state(RegistrationStates.waiting_for_contacts_choice)


@router.callback_query(F.data == "registration:add_contacts")
async def start_contacts_collection(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Start optional contacts collection."""
    await callback.message.edit_text(
        "📞 Введите номер телефона (или отправьте /skip чтобы пропустить):",
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_phone)


@router.callback_query(F.data == "registration:skip_contacts")
async def skip_contacts(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Skip contacts collection."""
    await callback.message.edit_text(
        "✅ Контакты пропущены. Вы можете добавить их позже "
        "в настройках профиля.",
    )
    await callback.answer()
    await state.clear()


@router.message(RegistrationStates.waiting_for_phone)
async def process_phone(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Process phone number."""
    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this

    skip_commands = ["/skip", "пропустить", "skip"]
    if message.text and message.text.strip().lower() in skip_commands:
        await state.update_data(phone=None)
        await state.set_state(RegistrationStates.waiting_for_email)
        await message.answer(
            "📧 Введите email (или отправьте /skip чтобы пропустить):",
        )
        return

    phone = message.text.strip() if message.text else ""

    # Basic phone validation (can be improved)
    if phone and len(phone) < 5:
        await message.answer(
            "❌ Неверный формат телефона!\n\n"
            "Введите корректный номер или /skip чтобы пропустить:"
        )
        return

    await state.update_data(phone=phone if phone else None)
    await state.set_state(RegistrationStates.waiting_for_email)

    if phone:
        await message.answer(
            "✅ Телефон сохранен!\n\n"
            "📧 Введите email (или отправьте /skip чтобы пропустить):",
        )
    else:
        await message.answer(
            "📧 Введите email (или отправьте /skip чтобы пропустить):",
        )


@router.message(RegistrationStates.waiting_for_email)
async def process_email(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Process email and save contacts."""
    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this

    skip_commands = ["/skip", "пропустить", "skip"]
    if message.text and message.text.strip().lower() in skip_commands:
        email = None
    else:
        email = message.text.strip() if message.text else None

        # Basic email validation
        if email and ("@" not in email or "." not in email):
            await message.answer(
                "❌ Неверный формат email!\n\n"
                "Введите корректный email или /skip чтобы пропустить:"
            )
            return

    # Get phone from state
    data = await state.get_data()
    phone = data.get("phone")

    # Update user with contacts
    user_service = UserService(session)
    await user_service.update_profile(
        user.id,
        phone=phone,
        email=email,
    )

    contacts_text = "✅ Контакты сохранены!\n\n"
    if phone:
        contacts_text += f"📞 Телефон: {phone}\n"
    if email:
        contacts_text += f"📧 Email: {email}\n"

    if not phone and not email:
        contacts_text = "✅ Регистрация завершена без контактов.\n\n"
        contacts_text += "Вы можете добавить их позже в настройках профиля."
    else:
        contacts_text += "\nВы можете изменить их позже в настройках профиля."

    await message.answer(
        contacts_text,
        reply_markup=main_menu_reply_keyboard(),
    )
    await state.clear()
