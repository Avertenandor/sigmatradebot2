"""
Start handler.

Handles /start command and user registration.
"""

from typing import Any

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Message,
    ReplyKeyboardRemove,
)
from loguru import logger
from sqlalchemy.exc import OperationalError, InterfaceError, DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.user_service import UserService
from bot.i18n.loader import get_translator, get_user_language
from bot.keyboards.reply import main_menu_reply_keyboard
from bot.states.registration import RegistrationStates

router = Router()


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Handle /start command with referral code support.

    Args:
        message: Telegram message
        session: Database session
        state: FSM state
        data: Additional data from middlewares
    """
    logger.info(
        f"=== CMD_START CALLED === user "
        f"{message.from_user.id if message.from_user else 'Unknown'}"
    )
    logger.info(f"Message text: {message.text}")

    # КРИТИЧНО: Всегда очищаем состояние при /start
    current_state = await state.get_state()
    if current_state:
        logger.info(f"Clearing FSM state: {current_state}")
    await state.clear()

    user: User | None = data.get("user")
    # Extract referral code from command args
    # Format: /start ref123456 or /start ref_123456 or /start ref_CODE
    referrer_telegram_id = None
    if message.text and len(message.text.split()) > 1:
        ref_arg = message.text.split()[1].strip()
        # Support formats: ref123456, ref_123456, ref-123456
        if ref_arg.startswith("ref"):
            try:
                # Extract value from ref code
                # Note: We remove 'ref', '_', '-' prefix/separators.
                # If the code itself contains '_' or '-', this might be an issue if we strip them globally.
                # But legacy IDs were digits.
                # New codes are urlsafe base64, which can contain '-' and '_'.
                # So we should be careful about stripping.
                
                # Better parsing strategy:
                # 1. Remove 'ref' prefix (case insensitive?)
                # 2. If starts with '_' or '-', remove ONE leading separator.
                
                clean_arg = ref_arg[3:] # Remove 'ref'
                if clean_arg.startswith("_") or clean_arg.startswith("-"):
                    clean_arg = clean_arg[1:]
                
                if clean_arg.isdigit():
                    # Legacy ID
                    referrer_telegram_id = int(clean_arg)
                    logger.info(
                        "Legacy referral ID detected",
                        extra={
                            "ref_arg": ref_arg,
                            "referrer_telegram_id": referrer_telegram_id,
                        },
                    )
                else:
                    # New Referral Code
                    # We need UserService here. 
                    # Note: Creating service inside handler is fine.
                    user_service = UserService(session)
                    referrer = await user_service.get_by_referral_code(clean_arg)
                    
                    if referrer:
                        referrer_telegram_id = referrer.telegram_id
                        logger.info(
                            "Referral code detected",
                            extra={
                                "ref_code": clean_arg,
                                "referrer_telegram_id": referrer_telegram_id,
                            },
                        )
                    else:
                        logger.warning(
                            "Referral code not found",
                            extra={"ref_code": clean_arg},
                        )

            except (ValueError, AttributeError) as e:
                logger.warning(
                    f"Invalid referral code format: {e}",
                    extra={"ref_code": ref_arg},
                )

    # Check if already registered
    if user:
        logger.info(
            f"cmd_start: registered user {user.telegram_id}, "
            f"clearing FSM state"
        )
        # КРИТИЧНО: очистим любое FSM состояние, чтобы /start всегда работал
        await state.clear()
        
        # R8-2: Reset bot_blocked flag if user successfully sent /start
        # (means user unblocked the bot)
        try:
            if hasattr(user, 'bot_blocked') and user.bot_blocked:
                from app.repositories.user_repository import UserRepository
                user_repo = UserRepository(session)
                await user_repo.update(user.id, bot_blocked=False)
                await session.commit()
                logger.info(
                    f"User {user.telegram_id} unblocked bot, flag reset in /start"
                )
        except Exception as reset_error:
            # Don't fail /start if flag reset fails
            logger.warning(f"Failed to reset bot_blocked flag: {reset_error}")

        # R13-3: Get user language for i18n
        user_language = await get_user_language(session, user.id)
        _ = get_translator(user_language)
        
        # Format balance properly (avoid scientific notation)
        balance_str = f"{user.balance:.8f}".rstrip('0').rstrip('.')
        if balance_str == '':
            balance_str = '0'

        # Escape username for Markdown to prevent TelegramBadRequest
        raw_username = user.username or _('common.user')
        safe_username = raw_username.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

        welcome_text = (
            f"{_('common.welcome_back', username=safe_username)}\n\n"
            f"{_('common.your_balance', balance=balance_str)}\n"
            f"{_('common.use_menu')}"
        )
        logger.debug("cmd_start: sending welcome with ReplyKeyboardRemove")
        # 1) Очистим старую клавиатуру
        await message.answer(
            welcome_text,
            parse_mode="Markdown",
            disable_web_page_preview=False,
            reply_markup=ReplyKeyboardRemove(),
        )
        logger.debug("cmd_start: sending main menu keyboard")
        # 2) И отправим главное меню отдельным сообщением
        # Get is_admin from middleware data
        is_admin = data.get("is_admin", False)
        logger.info(
            f"[START] cmd_start for registered user {user.telegram_id}: "
            f"is_admin={is_admin}, data keys: {list(data.keys())}"
        )
        # Get blacklist status if needed (try to get from middleware first)
        blacklist_entry = data.get("blacklist_entry")
        try:
            if blacklist_entry is None:
                from app.repositories.blacklist_repository import BlacklistRepository
                blacklist_repo = BlacklistRepository(session)
                blacklist_entry = await blacklist_repo.find_by_telegram_id(
                    user.telegram_id
                )
        except (OperationalError, InterfaceError, DatabaseError) as e:
            logger.error(
                f"Database error in /start while checking blacklist for user {user.telegram_id}: {e}",
                exc_info=True,
            )
            await message.answer(
                "⚠️ Системная ошибка. Попробуйте позже или обратитесь в поддержку."
            )
            return
        logger.info(
            f"[START] Creating keyboard for user {user.telegram_id} with "
            f"is_admin={is_admin}, "
            f"blacklist_entry={blacklist_entry is not None}"
        )
        # R13-3: Use i18n (already loaded above)
        await message.answer(
            _("common.choose_action"),
            reply_markup=main_menu_reply_keyboard(
                user=user,
                blacklist_entry=blacklist_entry,
                is_admin=is_admin,
            ),
        )
        logger.info(
            f"[START] Main menu keyboard sent successfully to user "
            f"{user.telegram_id}"
        )
        return

    # R1-3: Check blacklist for non-registered users (REGISTRATION_DENIED)
    # This check must happen BEFORE showing welcome message and setting FSM state
    blacklist_entry = data.get("blacklist_entry")
    try:
        if blacklist_entry is None:
            from app.repositories.blacklist_repository import BlacklistRepository
            blacklist_repo = BlacklistRepository(session)
            blacklist_entry = await blacklist_repo.find_by_telegram_id(
                message.from_user.id
            )
        
        if blacklist_entry and blacklist_entry.is_active:
            from app.models.blacklist import BlacklistActionType
            
            if blacklist_entry.action_type == BlacklistActionType.REGISTRATION_DENIED:
                logger.info(
                    f"[START] Registration denied for telegram_id {message.from_user.id}"
                )
                await message.answer(
                    "❌ Регистрация недоступна.\n\n"
                    "Обратитесь в поддержку для получения дополнительной информации."
                )
                await state.clear()
                return
    except (OperationalError, InterfaceError, DatabaseError) as e:
        logger.error(
            f"Database error in /start while checking blacklist for non-registered user {message.from_user.id}: {e}",
            exc_info=True,
        )
        await message.answer(
            "⚠️ Системная ошибка. Попробуйте позже или обратитесь в поддержку."
        )
        return

    # Not registered: покажем приветствие и сразу главное меню
    welcome_text = (
        "👋 **Добро пожаловать в SigmaTrade!**\n\n"
        "SigmaTrade — это платформа для получения вами вашего личного дохода "
        "в USDT на сети Binance Smart Chain (BEP-20).\n\n"
        "**Важно:**\n"
        "• Работа ведется только с сетью **BSC (BEP-20)**\n"
        "• Базовая валюта депозитов — **USDT BEP-20**\n\n"
        "🌐 **Официальный сайт:**\n"
        "[sigmatrade.org](https://sigmatrade.org/index.html#exchange)\n\n"
        "Для начала работы необходимо пройти регистрацию.\n\n"
        "📝 **Шаг 1:** Введите ваш BSC (BEP-20) адрес кошелька\n"
        "Формат: `0x...` (42 символа)\n\n"
        "⚠️ **КРИТИЧНО:** Указывайте только **ЛИЧНЫЙ** кошелек (Trust Wallet, MetaMask, SafePal или любой холодный кошелек).\n"
        "🚫 **НЕ указывайте** адрес биржи (Binance, Bybit), иначе выплаты могут быть утеряны!"
    )

    if referrer_telegram_id:
        # Save referrer to state for later use
        await state.update_data(referrer_telegram_id=referrer_telegram_id)
        welcome_text += (
            "\n\n✅ Реферальный код принят! "
            "После регистрации вы будете привязаны к пригласившему."
        )

    # 1) Очистим клавиатуру в приветствии
    await message.answer(
        welcome_text,
        parse_mode="Markdown",
        disable_web_page_preview=False,
        reply_markup=ReplyKeyboardRemove(),
    )
    # 2) Добавим большое главное меню отдельно
    # R13-3: Get user language for i18n (if user exists)
    user_language = "ru"  # Default
    if user:
        try:
            user_language = await get_user_language(session, user.id)
        except Exception as e:
            logger.warning(f"Failed to get user language, using default: {e}")
            pass
    _ = get_translator(user_language)
    
    # For unregistered users, is_admin will be False
    is_admin = data.get("is_admin", False)
    await message.answer(
        _("common.choose_action"),
        reply_markup=main_menu_reply_keyboard(
            user=user, blacklist_entry=None, is_admin=is_admin
        ),
    )

    await state.set_state(RegistrationStates.waiting_for_wallet)


@router.message(RegistrationStates.waiting_for_wallet)
async def process_wallet(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Process wallet address.

    Uses session_factory to ensure transaction is closed before FSM "
        "state change.

    Args:
        message: Telegram message
        state: FSM state
        data: Additional data including session_factory
    """
    # КРИТИЧНО: обрабатываем /start прямо здесь, не полагаясь на dispatcher
    if message.text and message.text.startswith("/start"):
        logger.info(
            "process_wallet: /start caught, clearing state, showing main menu"
        )
        await state.clear()
        # Сразу показываем главное меню
        user: User | None = data.get("user")
        is_admin = data.get("is_admin", False)
        # Получаем session из data
        session = data.get("session")
        # Try to get from middleware first
        blacklist_entry = data.get("blacklist_entry")
        # КРИТИЧНО: проверяем session перед использованием
        if blacklist_entry is None and user and session:
            try:
                from app.repositories.blacklist_repository import (
                    BlacklistRepository,
                )
                blacklist_repo = BlacklistRepository(session)
                blacklist_entry = await blacklist_repo.find_by_telegram_id(
                    user.telegram_id
                )
            except Exception as e:
                logger.warning(
                    f"Failed to get blacklist entry for user {user.telegram_id}: {e}"
                )
                blacklist_entry = None
        # R13-3: Get user language for i18n
        user_language = "ru"  # Default
        if user:
            try:
                user_language = await get_user_language(session, user.id)
            except Exception as e:
                logger.warning(f"Failed to get user language, using default: {e}")
        _ = get_translator(user_language)
        
        await message.answer(
            _("common.welcome"),
            reply_markup=ReplyKeyboardRemove(),
        )
        await message.answer(
            _("common.choose_action"),
            reply_markup=main_menu_reply_keyboard(
                user=user,
                blacklist_entry=blacklist_entry,
                is_admin=is_admin,
            ),
        )
        return

    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    # Handle "Регистрация" button specially while in waiting_for_wallet state
    # This prevents the loop where clicking "Registration" clears state and shows menu again
    if message.text == "📝 Регистрация":
        await message.answer(
            "📝 **Регистрация**\n\n"
            "Введите ваш BSC (BEP-20) адрес кошелька:\n"
            "Формат: `0x...` (42 символа)\n\n"
            "⚠️ Указывайте только **ЛИЧНЫЙ** кошелек (Trust Wallet, MetaMask, SafePal или холодный кошелек).\n"
            "🚫 **НЕ указывайте** адрес биржи!",
            parse_mode="Markdown",
        )
        return

    if is_menu_button(message.text):
        logger.debug(
            f"process_wallet: menu button {message.text}, showing main menu"
        )
        await state.clear()
        # Покажем главное меню сразу, не полагаясь на повторную диспетчеризацию
        user: User | None = data.get("user")
        is_admin = data.get("is_admin", False)
        # Получаем session из data
        session = data.get("session")
        blacklist_entry = None
        # КРИТИЧНО: проверяем session перед использованием
        if user and session:
            try:
                from app.repositories.blacklist_repository import (
                    BlacklistRepository,
                )
                blacklist_repo = BlacklistRepository(session)
                blacklist_entry = await blacklist_repo.find_by_telegram_id(
                    user.telegram_id
                )
            except Exception as e:
                logger.warning(
                    f"Failed to get blacklist entry for user {user.telegram_id}: {e}"
                )
                blacklist_entry = None
        await message.answer(
            "📊 Главное меню",
            reply_markup=main_menu_reply_keyboard(
                user=user,
                blacklist_entry=blacklist_entry,
                is_admin=is_admin,
            ),
        )
        return

    wallet_address = message.text.strip()

    # Check registration rate limit
    telegram_id = message.from_user.id if message.from_user else None
    if telegram_id:
        from bot.utils.operation_rate_limit import OperationRateLimiter

        redis_client = data.get("redis_client")
        rate_limiter = OperationRateLimiter(redis_client=redis_client)
        allowed, error_msg = await rate_limiter.check_registration_limit(
            telegram_id
        )
        if not allowed:
            await message.answer(error_msg or "Слишком много попыток регистрации")
            return

    # Validate wallet format using proper validation
    from app.utils.validation import validate_bsc_address

    if not validate_bsc_address(wallet_address, checksum=False):
        await message.answer(
            "❌ Неверный формат адреса!\n\n"
            "BSC адрес должен начинаться с '0x' и содержать 42 символа "
            "(0x + 40 hex символов).\n"
            "Попробуйте еще раз:"
        )
        return

    # R1-13: Check wallet blacklist
    session_factory = data.get("session_factory")
    if session_factory:
        try:
            async with session_factory() as session:
                async with session.begin():
                    from app.services.blacklist_service import BlacklistService
                    blacklist_service = BlacklistService(session)
                    if await blacklist_service.is_blacklisted(
                        wallet_address=wallet_address.lower()
                    ):
                        await message.answer(
                            "❌ Регистрация запрещена. Обращайтесь в поддержку."
                        )
                        await state.clear()
                        return
                    
                    # Check if wallet is already used by another user (Unique constraint)
                    from app.services.user_service import UserService
                    user_service = UserService(session)
                    existing_user = await user_service.get_by_wallet(wallet_address)
                    if existing_user:
                        telegram_id = message.from_user.id if message.from_user else None
                        if existing_user.telegram_id != telegram_id:
                             await message.answer(
                                "❌ Этот кошелек уже привязан к другому пользователю!\n"
                                "Пожалуйста, используйте другой кошелек."
                            )
                             return
                        else:
                            await message.answer(
                                "ℹ️ Этот кошелек уже привязан к вашему аккаунту.\n"
                                "Используйте /start для входа."
                            )
                            await state.clear()
                            return

        except (OperationalError, InterfaceError, DatabaseError) as e:
            logger.error(
                f"Database error checking wallet blacklist: {e}", exc_info=True
            )
            await message.answer(
                "⚠️ Системная ошибка. Попробуйте позже или обратитесь в поддержку."
            )
            return

    # SHORT transaction scope - check wallet and close BEFORE FSM state change
    if not session_factory:
        # Fallback to old session for backward compatibility
        session = data.get("session")
        if not session:
            await message.answer(
                "❌ Системная ошибка. Отправьте /start или "
                "обратитесь в поддержку."
            )
            return
        
        user_service = UserService(session)
        
        # Check if wallet is already used
        existing = await user_service.get_by_wallet(wallet_address)
    else:
        # NEW pattern: short transaction
        async with session_factory() as session:
            async with session.begin():
                user_service = UserService(session)
                existing = await user_service.get_by_wallet(wallet_address)
        # Transaction closed here, before FSM state change

    # R1-12: Кошелёк уже привязан к существующему пользователю
    if existing:
        telegram_id = message.from_user.id if message.from_user else None
        # Если это тот же telegram_id — предлагаем /start и используем старый аккаунт
        if telegram_id and existing.telegram_id == telegram_id:
            await message.answer(
                "ℹ️ Этот кошелек уже привязан к вашему аккаунту.\n\n"
                "Используйте команду /start для входа в систему."
            )
            await state.clear()
            return
        # Если другой telegram_id — выводим сообщение, что кошелёк занят
        else:
            await message.answer(
                "❌ Этот кошелек уже зарегистрирован другим пользователем!\n\n"
                "Используйте другой адрес:"
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
    message: Message,
    state: FSMContext,
    session: AsyncSession | None = None,
    **data: Any,
) -> None:
    """
    Process financial password.

    Args:
        message: Telegram message
        state: FSM state
        session: Database session (optional, can be from data)
        data: Additional data from middlewares
    """
    # КРИТИЧНО: пропускаем /start к основному обработчику
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Позволяем CommandStart() обработать это

    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if is_menu_button(message.text):
        await state.clear()
        # Get session from data if not provided
        if session is None:
            session = data.get("session")
        user: User | None = data.get("user")
        is_admin = data.get("is_admin", False)
        from app.repositories.blacklist_repository import BlacklistRepository
        if session:
            blacklist_repo = BlacklistRepository(session)
            blacklist_entry = None
            if user:
                blacklist_entry = await blacklist_repo.find_by_telegram_id(
            user.telegram_id
        )
            await message.answer(
                "📊 Главное меню",
                reply_markup=main_menu_reply_keyboard(
                    user=user,
                    blacklist_entry=blacklist_entry,
                    is_admin=is_admin
                ),
            )
        else:
            # Fallback if no session
            await message.answer(
                "📊 Главное меню",
                reply_markup=main_menu_reply_keyboard(
                    user=user, blacklist_entry=None, is_admin=is_admin
                ),
            )
        return

    password = message.text.strip()

    # Validate password
    if len(password) < 6:
        await message.answer(
            "❌ Пароль слишком короткий!\n\n"
            "Минимальная длина: 6 символов.\n"
            "Попробуйте еще раз:"
        )
        return

    # Delete message with password (safe delete)
    try:
        await message.delete()
    except Exception:
        pass  # Message already deleted or not available

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
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Process password confirmation and complete registration.

    Uses session_factory for short transaction during user registration.

    Args:
        message: Telegram message
        state: FSM state
        data: Additional data including session_factory
    """
    # КРИТИЧНО: пропускаем /start к основному обработчику
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Позволяем CommandStart() обработать это

    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if is_menu_button(message.text):
        await state.clear()
        user: User | None = data.get("user")
        is_admin = data.get("is_admin", False)
        # Получаем session из data
        session = data.get("session")
        blacklist_entry = None
        # КРИТИЧНО: проверяем session перед использованием
        if user and session:
            try:
                from app.repositories.blacklist_repository import (
                    BlacklistRepository,
                )
                blacklist_repo = BlacklistRepository(session)
                blacklist_entry = await blacklist_repo.find_by_telegram_id(
                    user.telegram_id
                )
            except Exception as e:
                logger.warning(
                    f"Failed to get blacklist entry for user {user.telegram_id}: {e}"
                )
                blacklist_entry = None
        await message.answer(
            "📊 Главное меню",
            reply_markup=main_menu_reply_keyboard(
                user=user,
                blacklist_entry=blacklist_entry,
                is_admin=is_admin,
            ),
        )
        return

    confirmation = message.text.strip()

    # Delete message with password (safe delete)
    try:
        await message.delete()
    except Exception:
        pass  # Message already deleted or not available

    # Get data from state
    state_data = await state.get_data()
    password = state_data.get("financial_password")

    # Check if passwords match
    if confirmation != password:
        await message.answer(
            "❌ Пароли не совпадают!\n\nВведите пароль еще раз:"
        )
        await state.set_state(
            RegistrationStates.waiting_for_financial_password
        )
        return

    # SHORT transaction for user registration
    wallet_address = state_data.get("wallet_address")
    referrer_telegram_id = state_data.get("referrer_telegram_id")

    # Hash financial password with bcrypt
    import bcrypt
    hashed_password = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")

    # Normalize wallet address to checksum format
    from app.utils.validation import normalize_bsc_address
    try:
        wallet_address = normalize_bsc_address(wallet_address)
    except ValueError as e:
        await message.answer(
            f"❌ Ошибка валидации адреса кошелька:\n{str(e)}\n\n"
            "Попробуйте начать заново: /start"
        )
        await state.clear()
        return

    session_factory = data.get("session_factory")
    if not session_factory:
        # Fallback to old session for backward compatibility
        session = data.get("session")
        if not session:
            await message.answer(
                "❌ Системная ошибка. Отправьте /start или "
                "обратитесь в поддержку."
            )
            await state.clear()
            return
        user_service = UserService(session)
        try:
            user = await user_service.register_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                wallet_address=wallet_address,
                financial_password=hashed_password,
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
    else:
        # NEW pattern: short transaction for registration
        user = None
        try:
            async with session_factory() as session:
                async with session.begin():
                    user_service = UserService(session)
                    user = await user_service.register_user(
                        telegram_id=message.from_user.id,
                        username=message.from_user.username,
                        wallet_address=wallet_address,
                        financial_password=hashed_password,
                        referrer_telegram_id=referrer_telegram_id,
                    )
            # Transaction closed here
        except ValueError as e:
            error_msg = str(e)
            
            # FIX: Handle "User already registered" as success (Double Submit race condition)
            if error_msg == "User already registered":
                logger.info(
                    f"Double registration attempt caught for user {message.from_user.id} - checking existing user"
                )
                # Try to fetch existing user to confirm it's really them
                async with session_factory() as session:
                    user_service = UserService(session)
                    user = await user_service.get_by_telegram_id(message.from_user.id)
                
                if user:
                    logger.info(
                        f"User {user.id} found, treating double registration error as success"
                    )
                    # Proceed to success flow below
                else:
                    # User not found but error says registered? Weird race or different user.
                    await message.answer(
                        "❌ Ошибка: Пользователь уже зарегистрирован, но данные не найдены. Обратитесь в поддержку."
                    )
                    await state.clear()
                    return

            # Check if it's a blacklist error
            elif error_msg.startswith("BLACKLISTED:"):
                action_type = error_msg.split(":")[1]
                from app.models.blacklist import BlacklistActionType

                if action_type == BlacklistActionType.REGISTRATION_DENIED:
                    await message.answer(
                        "Здравствуйте, по решению участников нашего "
                        "сообщества вам отказано в регистрации в нашем "
                        "боте и других инструментах нашего сообщества."
                    )
                else:
                    await message.answer(
                        "❌ Ошибка регистрации. Обратитесь в поддержку."
                    )
                await state.clear()
                return
            else:
                await message.answer(
                    f"❌ Ошибка регистрации:\n{error_msg}\n\n"
                    "Попробуйте начать заново: /start"
                )
                await state.clear()
                return

    # Registration successful
    if not user:
        # Should not happen if logic above is correct
        await message.answer("❌ Неизвестная ошибка регистрации.")
        await state.clear()
        return

    logger.info(
        "User registered successfully",
        extra={
            "user_id": user.id,
            "telegram_id": message.from_user.id,
        },
    )

    # R1-19: Сохраняем plain password в Redis на 1 час для повторного показа
    redis_client = data.get("redis_client")
    if redis_client and password:
        try:
            password_key = f"password:plain:{user.id}"
            # Сохраняем пароль на 1 час (3600 секунд)
            await redis_client.setex(password_key, 3600, password)
            logger.info(
                f"Plain password stored in Redis for user {user.id} (1 hour TTL)"
            )
        except Exception as e:
            logger.warning(
                f"Failed to store plain password in Redis for user {user.id}: {e}"
            )

    # Get is_admin from middleware data
    is_admin = data.get("is_admin", False)
    # Получаем session из data для получения blacklist_entry
    session = data.get("session")
    blacklist_entry = None
    if session:
        from app.repositories.blacklist_repository import BlacklistRepository
        blacklist_repo = BlacklistRepository(session)
        blacklist_entry = await blacklist_repo.find_by_telegram_id(
            user.telegram_id
        )
    
    # R1-19: Добавляем кнопку для повторного показа пароля
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    show_password_button = InlineKeyboardButton(
        text="🔑 Показать пароль ещё раз",
        callback_data=f"show_password_{user.id}"
    )
    password_keyboard = InlineKeyboardMarkup(inline_keyboard=[[show_password_button]])
    
    await message.answer(
        "🎉 Регистрация завершена!\n\n"
        f"Ваш ID: {user.id}\n"
        f"Кошелек: {user.masked_wallet}\n\n"
        "Добро пожаловать в SigmaTrade! 🚀\n\n"
        "⚠️ **Важно:** Сохраните ваш финансовый пароль в безопасном месте!\n"
        "Он понадобится для подтверждения финансовых операций.",
        reply_markup=password_keyboard,
    )
    
    # R13-3: Get user language for i18n
    user_language = await get_user_language(session, user.id)
    _ = get_translator(user_language)
    
    # Отправляем главное меню отдельным сообщением
    await message.answer(
        _("common.choose_action"),
        reply_markup=main_menu_reply_keyboard(
            user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
        ),
    )

    # Ask if user wants to provide contacts (optional but recommended)
    from bot.keyboards.reply import contacts_choice_keyboard

    await message.answer(
        "📝 **Рекомендуем оставить контакты!**\n\n"
        "🔒 **Зачем это нужно?**\n"
        "Если ваш Telegram-аккаунт будет угнан или заблокирован, "
        "мы сможем связаться с вами и помочь восстановить доступ к средствам.\n\n"
        "⚠️ **Важно:** Указывайте *реальные* данные!\n"
        "• Телефон: ваш действующий номер\n"
        "• Email: почта, к которой у вас есть доступ\n\n"
        "Хотите оставить контакты?",
        parse_mode="Markdown",
        reply_markup=contacts_choice_keyboard(),
    )

    await state.set_state(RegistrationStates.waiting_for_contacts_choice)


@router.message(RegistrationStates.waiting_for_contacts_choice)
async def handle_contacts_choice(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle contacts choice during registration."""
    # КРИТИЧНО: обрабатываем /start прямо здесь
    if message.text and message.text.startswith("/start"):
        logger.info(
            "handle_contacts_choice: /start caught, clearing state"
        )
        await state.clear()
        return  # Позволяем CommandStart() обработать это
    
    if message.text == "✅ Да, оставить контакты":
        await message.answer(
            "📞 **Введите номер телефона**\n\n"
            "Формат: `+7XXXXXXXXXX` или `+380XXXXXXXXX`\n"
            "(международный формат с кодом страны)\n\n"
            "Или отправьте /skip чтобы пропустить:",
            parse_mode="Markdown",
        )
        await state.set_state(RegistrationStates.waiting_for_phone)
    # Нормализуем текст: удаляем FE0F (emoji variation selector)
    elif message.text and message.text.replace("\ufe0f", "") in (
        "⏭ Пропустить", "⏭️ Пропустить"
    ):
        await message.answer(
            "✅ Контакты пропущены.\n\n"
            "⚠️ Рекомендуем добавить их позже в настройках профиля "
            "для защиты вашего аккаунта.",
        )
        await state.clear()
    else:
        # If user sent something else, show menu again
        from bot.keyboards.reply import contacts_choice_keyboard
        await message.answer(
            "📝 **Рекомендуем оставить контакты!**\n\n"
            "🔒 Если ваш Telegram будет угнан, мы сможем помочь "
            "восстановить доступ к средствам.\n\n"
            "Хотите оставить контакты?",
            parse_mode="Markdown",
            reply_markup=contacts_choice_keyboard(),
        )


@router.message(RegistrationStates.waiting_for_phone)
async def process_phone(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Process phone number."""
    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if is_menu_button(message.text):
        await state.clear()
        user: User | None = data.get("user")
        is_admin = data.get("is_admin", False)
        from app.repositories.blacklist_repository import BlacklistRepository
        blacklist_repo = BlacklistRepository(session)
        blacklist_entry = None
        if user:
            blacklist_entry = await blacklist_repo.find_by_telegram_id(
            user.telegram_id
        )
        await message.answer(
            "📊 Главное меню",
            reply_markup=main_menu_reply_keyboard(
                user=user,
                blacklist_entry=blacklist_entry,
                is_admin=is_admin,
            ),
        )
        return

    skip_commands = ["/skip", "пропустить", "skip"]
    if message.text and message.text.strip().lower() in skip_commands:
        await state.update_data(phone=None)
        await state.set_state(RegistrationStates.waiting_for_email)
        await message.answer(
            "📧 Введите email (или отправьте /skip чтобы пропустить):",
        )
        return

    phone = message.text.strip() if message.text else ""

    # Strict phone validation
    import re
    # Remove spaces, dashes, parentheses
    phone_clean = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Must start with + and contain only digits after
    phone_pattern = r'^\+\d{10,15}$'
    if phone and not re.match(phone_pattern, phone_clean):
        await message.answer(
            "❌ **Неверный формат телефона!**\n\n"
            "Введите номер в международном формате:\n"
            "• `+7XXXXXXXXXX` (Россия)\n"
            "• `+380XXXXXXXXX` (Украина)\n"
            "• `+375XXXXXXXXX` (Беларусь)\n\n"
            "Или отправьте /skip чтобы пропустить:",
            parse_mode="Markdown",
        )
        return
    
    # Normalize phone
    phone = phone_clean if phone else ""

    await state.update_data(phone=phone if phone else None)
    await state.set_state(RegistrationStates.waiting_for_email)

    if phone:
        await message.answer(
            "✅ Телефон сохранён!\n\n"
            "📧 **Введите email**\n\n"
            "Формат: `example@mail.com`\n"
            "(реальный адрес, к которому у вас есть доступ)\n\n"
            "Или отправьте /skip чтобы пропустить:",
            parse_mode="Markdown",
        )
    else:
        await message.answer(
            "📧 **Введите email**\n\n"
            "Формат: `example@mail.com`\n"
            "(реальный адрес, к которому у вас есть доступ)\n\n"
            "Или отправьте /skip чтобы пропустить:",
            parse_mode="Markdown",
        )


@router.message(RegistrationStates.waiting_for_email)
async def process_email(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Process email and save contacts."""
    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if is_menu_button(message.text):
        await state.clear()
        user: User | None = data.get("user")
        is_admin = data.get("is_admin", False)
        from app.repositories.blacklist_repository import BlacklistRepository
        blacklist_repo = BlacklistRepository(session)
        blacklist_entry = None
        if user:
            blacklist_entry = await blacklist_repo.find_by_telegram_id(
            user.telegram_id
        )
        await message.answer(
            "📊 Главное меню",
            reply_markup=main_menu_reply_keyboard(
                user=user,
                blacklist_entry=blacklist_entry,
                is_admin=is_admin,
            ),
        )
        return

    skip_commands = ["/skip", "пропустить", "skip"]
    if message.text and message.text.strip().lower() in skip_commands:
        email = None
    else:
        email = message.text.strip().lower() if message.text else None

        # Strict email validation
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if email and not re.match(email_pattern, email):
            await message.answer(
                "❌ **Неверный формат email!**\n\n"
                "Введите корректный адрес, например:\n"
                "• `user@gmail.com`\n"
                "• `name@mail.ru`\n"
                "• `example@yandex.ru`\n\n"
                "Или отправьте /skip чтобы пропустить:",
                parse_mode="Markdown",
            )
            return

    # Get phone from state (don't override data parameter)
    state_data = await state.get_data()
    phone = state_data.get("phone")

    # Update user with contacts
    # Get user from middleware data (parameter), not from state
    user_service = UserService(session)
    current_user: User | None = data.get("user")
    if not current_user:
        logger.error("process_email: user missing in middleware data")
        await message.answer(
            "❌ Ошибка контекста пользователя. Повторите /start"
        )
        return
    await user_service.update_profile(
        current_user.id,
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

    # Get is_admin from middleware data
    is_admin = data.get("is_admin", False)
    from app.repositories.blacklist_repository import BlacklistRepository
    blacklist_repo = BlacklistRepository(session)
    blacklist_entry = None
    if current_user:
        blacklist_entry = await blacklist_repo.find_by_telegram_id(
            current_user.telegram_id
        )
    await message.answer(
        contacts_text,
        reply_markup=main_menu_reply_keyboard(
            user=current_user,
            blacklist_entry=blacklist_entry,
            is_admin=is_admin,
        ),
    )
    await state.clear()


@router.callback_query(F.data.startswith("show_password_"))
async def handle_show_password_again(
    callback: CallbackQuery,
    **data: Any,
) -> None:
    """
    R1-19: Показать финансовый пароль ещё раз (в течение часа после регистрации).
    
    Args:
        callback: Callback query
        data: Handler data
    """
    # Извлекаем user_id из callback_data
    user_id_str = callback.data.replace("show_password_", "")
    try:
        user_id = int(user_id_str)
    except ValueError:
        await callback.answer("❌ Ошибка: неверный формат запроса", show_alert=True)
        return
    
    # Проверяем, что пользователь существует и это его запрос
    user: User | None = data.get("user")
    if not user or user.id != user_id:
        await callback.answer(
            "❌ Ошибка: доступ запрещен",
            show_alert=True
        )
        return
    
    # Получаем пароль из Redis
    redis_client = data.get("redis_client")
    if not redis_client:
        await callback.answer(
            "⚠️ Пароль больше недоступен (прошло более 1 часа с момента регистрации).\n\n"
            "Используйте функцию восстановления пароля в настройках.",
            show_alert=True
        )
        return
    
    try:
        password_key = f"password:plain:{user.id}"
        plain_password = await redis_client.get(password_key)
        
        if not plain_password:
            await callback.answer(
                "⚠️ Пароль больше недоступен (прошло более 1 часа с момента регистрации).\n\n"
                "Используйте функцию восстановления пароля в настройках.",
                show_alert=True
            )
            return
        
        # Показываем пароль в alert
        await callback.answer(
            f"🔑 Ваш финансовый пароль:\n\n{plain_password}\n\n"
            "⚠️ Сохраните его сейчас! Он больше не будет показан.",
            show_alert=True
        )
        
        logger.info(
            f"User {user.id} requested to show password again (within 1 hour window)"
        )
    except Exception as e:
        logger.error(
            f"Error retrieving plain password from Redis for user {user.id}: {e}",
            exc_info=True
        )
        await callback.answer(
            "❌ Ошибка при получении пароля. Обратитесь в поддержку.",
            show_alert=True
        )
