"""
Reply keyboards.

Reply keyboard builders for main navigation.
"""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from loguru import logger

from app.models.blacklist import Blacklist, BlacklistActionType
from app.models.user import User


def main_menu_reply_keyboard(
    user: User | None = None,
    blacklist_entry: Blacklist | None = None,
    is_admin: bool = False,
) -> ReplyKeyboardMarkup:
    """
    Main menu reply keyboard.

    Conditionally shows buttons based on user status (e.g., blocked, admin, unregistered).

    Args:
        user: The current user object (optional). If None, shows reduced menu for unregistered users.
        blacklist_entry: The user's blacklist entry, if any (optional).
        is_admin: Whether the user is an admin (optional).

    Returns:
        ReplyKeyboardMarkup with main menu buttons
    """
    # Safely access telegram_id
    user_id = user.id if user else None
    
    # Fix for AttributeError: 'User' object has no attribute 'telegram_id'
    # In fallback handler, message.from_user is a Telegram User object (aiogram), 
    # which has 'id', NOT 'telegram_id'.
    # Our database User model (app.models.user) has 'telegram_id'.
    # We need to handle both cases.
    telegram_id = None
    if user:
        if hasattr(user, 'telegram_id'):
            telegram_id = user.telegram_id
        elif hasattr(user, 'id'):
            telegram_id = user.id
            
    logger.debug(
        f"[KEYBOARD] main_menu_reply_keyboard called: "
        f"user_id={user_id}, telegram_id={telegram_id}, "
        f"is_admin={is_admin}, "
        f"blacklist_active={blacklist_entry.is_active if blacklist_entry else False}"
    )

    builder = ReplyKeyboardBuilder()

    # If user is blocked (with appeal option), show only appeal button
    if (
        user
        and blacklist_entry
        and blacklist_entry.is_active
        and blacklist_entry.action_type == BlacklistActionType.BLOCKED
    ):
        # Keep this on INFO as it's a rare security event
        logger.info(f"[KEYBOARD] User {telegram_id} is blocked, showing appeal button only")
        builder.row(
            KeyboardButton(text="📝 Подать апелляцию"),
        )
    elif user is None:
        # Reduced menu for unregistered users
        logger.debug(f"[KEYBOARD] Building reduced menu for unregistered user {telegram_id}")
        builder.row(
            KeyboardButton(text="📖 Инструкции"),
        )
        builder.row(
            KeyboardButton(text="💬 Поддержка"),
        )
        builder.row(
            KeyboardButton(text="📝 Регистрация"),
        )
    else:
        # Standard menu for registered users
        logger.debug(f"[KEYBOARD] Building standard menu for user {telegram_id}")
        builder.row(
            KeyboardButton(text="💰 Депозит"),
            KeyboardButton(text="💸 Вывод"),
        )
        builder.row(
            KeyboardButton(text="📦 Мои депозиты"),
        )
        builder.row(
            KeyboardButton(text="👥 Рефералы"),
            KeyboardButton(text="📊 Баланс"),
        )
        builder.row(
            KeyboardButton(text="💬 Поддержка"),
            KeyboardButton(text="⚙️ Настройки"),
        )
        builder.row(
            KeyboardButton(text="📖 Инструкции"),
            KeyboardButton(text="📜 История"),
        )
        builder.row(
            KeyboardButton(text="✅ Пройти верификацию"),
        )
        builder.row(
            KeyboardButton(text="🔑 Восстановить финпароль"),
        )

        # Add admin panel button for admins
        if is_admin:
            logger.info(f"[KEYBOARD] Adding admin panel button for user {telegram_id}")
            builder.row(
                KeyboardButton(text="👑 Админ-панель"),
            )
            # Add master key management button for super admin (telegram_id: 1040687384)
            # This button is accessible WITHOUT master key authentication
            logger.info(f"[KEYBOARD] AFTER admin panel button, before master key check")
            logger.info(
                f"[KEYBOARD] Checking master key button: "
                f"telegram_id={telegram_id}, type={type(telegram_id)}, "
                f"equals={telegram_id == 1040687384}"
            )
            if telegram_id == 1040687384:
                logger.info(
                    f"[KEYBOARD] Adding master key management button "
                    f"for super admin {telegram_id}"
                )
                builder.row(
                    KeyboardButton(text="🔑 Управление мастер-ключом"),
                )
            else:
                logger.info(
                    f"[KEYBOARD] NOT adding master key button: "
                    f"telegram_id={telegram_id} != 1040687384"
                )
        else:
            logger.info(f"[KEYBOARD] NOT adding admin panel button (is_admin={is_admin}) for user {telegram_id}")

    keyboard = builder.as_markup(resize_keyboard=True)
    logger.info(f"[KEYBOARD] Keyboard created for user {telegram_id}, buttons count: {len(keyboard.keyboard)}")
    return keyboard


def support_keyboard() -> ReplyKeyboardMarkup:
    """
    Support menu reply keyboard.

    Returns:
        ReplyKeyboardMarkup with support options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="✉️ Создать обращение"),
    )
    builder.row(
        KeyboardButton(text="📋 Мои обращения"),
    )
    builder.row(
        KeyboardButton(text="❓ FAQ"),
    )
    # Покажем и "Назад", и явную кнопку выхода в главное меню —
    # пользователи привыкли к обоим вариантам.
    builder.row(
        KeyboardButton(text="⬅ Назад"),
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def deposit_keyboard(
    levels_status: dict[int, dict] | None = None,
) -> ReplyKeyboardMarkup:
    """
    Deposit menu reply keyboard with status indicators.

    Args:
        levels_status: Optional dict with level statuses from DepositValidationService.get_available_levels()

    Returns:
        ReplyKeyboardMarkup with deposit options
    """
    builder = ReplyKeyboardBuilder()

    # Default amounts if statuses not provided
    default_amounts = {1: 10, 2: 50, 3: 100, 4: 150, 5: 300}
    
    for level in [1, 2, 3, 4, 5]:
        if levels_status and level in levels_status:
            level_info = levels_status[level]
            amount = level_info["amount"]
            status = level_info["status"]
            status_text = level_info.get("status_text", "")
            
            # Build button text with status indicator
            if status == "active":
                button_text = f"✅ Level {level} ({amount} USDT) - Активен"
            elif status == "available":
                button_text = f"💰 Пополнить Level {level} ({amount} USDT)"
            else:
                # unavailable - show reason in button
                error = level_info.get("error", "")
                if "необходимо сначала купить" in error:
                    button_text = f"🔒 Level {level} ({amount} USDT) - Нет предыдущего"
                elif "необходимо минимум" in error:
                    button_text = f"🔒 Level {level} ({amount} USDT) - Нет партнёров"
                else:
                    button_text = f"🔒 Level {level} ({amount} USDT) - Недоступен"
        else:
            # Fallback to default
            amount = default_amounts[level]
            button_text = f"💰 Пополнить Level {level} ({amount} USDT)"
        
        builder.row(KeyboardButton(text=button_text))

    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def withdrawal_keyboard() -> ReplyKeyboardMarkup:
    """
    Withdrawal menu reply keyboard.

    Returns:
        ReplyKeyboardMarkup with withdrawal options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="💸 Вывести всю сумму"),
    )
    builder.row(
        KeyboardButton(text="💵 Вывести указанную сумму"),
    )
    builder.row(
        KeyboardButton(text="📜 История выводов"),
    )
    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def referral_keyboard() -> ReplyKeyboardMarkup:
    """
    Referral menu reply keyboard.

    Returns:
        ReplyKeyboardMarkup with referral options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="👥 Мои рефералы"),
    )
    builder.row(
        KeyboardButton(text="💰 Мой заработок"),
    )
    builder.row(
        KeyboardButton(text="📊 Статистика рефералов"),
    )
    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def wallet_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Wallet menu keyboard.
    
    Returns:
        ReplyKeyboardMarkup with wallet options
    """
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🔄 Сменить кошелек"))
    builder.row(KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="📊 Главное меню"))
    return builder.as_markup(resize_keyboard=True)


def settings_keyboard(language: str | None = None) -> ReplyKeyboardMarkup:
    """
    Settings menu reply keyboard.

    Returns:
        ReplyKeyboardMarkup with settings options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="👤 Мой профиль"),
    )
    builder.row(
        KeyboardButton(text="💳 Мой кошелек"),
    )
    builder.row(
        KeyboardButton(text="🔔 Настройки уведомлений"),
    )
    builder.row(
        KeyboardButton(text="📝 Обновить контакты"),
    )
    builder.row(
        KeyboardButton(text="🌐 Изменить язык"),
    )
    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def contact_update_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Contact update menu keyboard.
    
    Returns:
        ReplyKeyboardMarkup with contact update options
    """
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="📞 Обновить телефон"),
    )
    builder.row(
        KeyboardButton(text="📧 Обновить email"),
    )
    builder.row(
        KeyboardButton(text="📝 Обновить оба"),
    )
    builder.row(
        KeyboardButton(text="◀️ Назад"),
        KeyboardButton(text="🏠 Главное меню"),
    )
    
    return builder.as_markup(resize_keyboard=True)


def contact_input_keyboard() -> ReplyKeyboardMarkup:
    """
    Contact input keyboard with skip option.
    
    Returns:
        ReplyKeyboardMarkup with skip and navigation options
    """
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="⏭ Пропустить"),
    )
    builder.row(
        KeyboardButton(text="◀️ Назад"),
        KeyboardButton(text="🏠 Главное меню"),
    )
    
    return builder.as_markup(resize_keyboard=True)


def get_admin_keyboard_from_data(data: dict) -> ReplyKeyboardMarkup:
    """
    Get admin keyboard with correct is_super_admin flag from handler data.

    Args:
        data: Handler data dict

    Returns:
        ReplyKeyboardMarkup with admin options
    """
    is_super_admin = data.get("is_super_admin", False)
    return admin_keyboard(is_super_admin=is_super_admin)


def admin_keyboard(is_super_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    Admin panel reply keyboard.

    Args:
        is_super_admin: Whether current admin is super admin

    Returns:
        ReplyKeyboardMarkup with admin options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="📊 Статистика"),
    )
    builder.row(
        KeyboardButton(text="👥 Управление пользователями"),
    )
    builder.row(
        KeyboardButton(text="💸 Заявки на вывод"),
    )
    builder.row(
        KeyboardButton(text="📢 Рассылка"),
        KeyboardButton(text="🆘 Техподдержка"),
    )
    builder.row(
        KeyboardButton(text="🔐 Управление кошельком"),
        KeyboardButton(text="📡 Блокчейн Настройки"),
    )
    builder.row(
        KeyboardButton(text="🚫 Управление черным списком"),
        KeyboardButton(text="🔑 Восстановление пароля"),
    )
    builder.row(
        KeyboardButton(text="💰 Управление депозитами"),
    )
    builder.row(
        KeyboardButton(text="📝 Просмотр сообщений пользователей"),
    )
    builder.row(
        KeyboardButton(text="💰 Финансовая отчётность"),
    )
    
    # Add admin management button only for super_admin
    if is_super_admin:
        builder.row(
            KeyboardButton(text="👥 Управление админами"),
        )
        # Master key management - only for specific super admin (checked in handler)
        builder.row(
            KeyboardButton(text="🔑 Управление мастер-ключом"),
        )
    
    builder.row(
        KeyboardButton(text="◀️ Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_users_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin users management keyboard.

    Returns:
        ReplyKeyboardMarkup with user management options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="🔍 Найти пользователя"),
    )
    builder.row(
        KeyboardButton(text="👥 Список пользователей"),
    )
    builder.row(
        KeyboardButton(text="🚫 Заблокировать пользователя"),
    )
    builder.row(
        KeyboardButton(text="⚠️ Терминировать аккаунт"),
    )
    builder.row(
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_withdrawals_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin withdrawals management keyboard.

    Returns:
        ReplyKeyboardMarkup with withdrawal management options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="⏳ Ожидающие выводы"),
    )
    builder.row(
        KeyboardButton(text="✅ Одобренные выводы"),
    )
    builder.row(
        KeyboardButton(text="❌ Отклоненные выводы"),
    )
    builder.row(
        KeyboardButton(text="⚙️ Настройки выплат"),
    )
    builder.row(
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def confirmation_keyboard() -> ReplyKeyboardMarkup:
    """
    Simple Yes/No confirmation keyboard.

    Returns:
        ReplyKeyboardMarkup with Yes/No options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="✅ Да"),
        KeyboardButton(text="❌ Нет"),
    )

    return builder.as_markup(resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Simple cancel keyboard.

    Returns:
        ReplyKeyboardMarkup with cancel option
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="❌ Отмена"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_wallet_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin wallet management keyboard.

    Returns:
        ReplyKeyboardMarkup with wallet management options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="📊 Статус кошельков"),
    )
    builder.row(
        KeyboardButton(text="📥 Настроить кошелек для входа"),
    )
    builder.row(
        KeyboardButton(text="📤 Настроить кошелек для выдачи"),
    )
    builder.row(
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_broadcast_button_choice_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin broadcast button choice keyboard.

    Returns:
        ReplyKeyboardMarkup with button options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="✅ Добавить кнопку"),
        KeyboardButton(text="🚀 Отправить без кнопки"),
    )
    builder.row(
        KeyboardButton(text="❌ Отмена"),
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_broadcast_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin broadcast cancel keyboard.

    Returns:
        ReplyKeyboardMarkup with cancel option
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="❌ Отмена"),
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_broadcast_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin broadcast keyboard.

    Returns:
        ReplyKeyboardMarkup with broadcast options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="❌ Отмена"),
    )
    builder.row(
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_support_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin support keyboard.

    Returns:
        ReplyKeyboardMarkup with support options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="📋 Список обращений"),
        KeyboardButton(text="🔍 Найти обращение"),
    )
    builder.row(
        KeyboardButton(text="📊 Статистика"),
        KeyboardButton(text="🙋‍♂️ Мои задачи"),
    )
    builder.row(
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_support_ticket_keyboard() -> ReplyKeyboardMarkup:
    """
    Keyboard for viewing a specific ticket.

    Returns:
        ReplyKeyboardMarkup with ticket actions
    """
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📝 Ответить"))
    builder.row(KeyboardButton(text="🔒 Закрыть"), KeyboardButton(text="↩️ Переоткрыть"))
    builder.row(KeyboardButton(text="✋ Взять в работу"))
    builder.row(KeyboardButton(text="◀️ Назад к списку"), KeyboardButton(text="👑 Админ-панель"))
    return builder.as_markup(resize_keyboard=True)


def admin_blacklist_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin blacklist management keyboard.

    Returns:
        ReplyKeyboardMarkup with blacklist management options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="➕ Добавить в blacklist"),
    )
    builder.row(
        KeyboardButton(text="🗑️ Удалить из blacklist"),
    )
    builder.row(
        KeyboardButton(text="📝 Редактировать тексты"),
    )
    builder.row(
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_management_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin management keyboard (for managing admins).

    Returns:
        ReplyKeyboardMarkup with admin management options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="➕ Добавить админа"),
    )
    builder.row(
        KeyboardButton(text="📋 Список админов"),
    )
    builder.row(
        KeyboardButton(text="🗑️ Удалить админа"),
    )
    builder.row(
        KeyboardButton(text="🛑 Экстренно заблокировать админа"),
    )
    builder.row(
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_deposit_settings_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin deposit settings keyboard.

    Returns:
        ReplyKeyboardMarkup with deposit settings options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="⚙️ Настроить уровни депозитов"),
    )
    builder.row(
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_deposit_management_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin deposit management main menu keyboard.

    Returns:
        ReplyKeyboardMarkup with deposit management options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="📊 Статистика по депозитам"),
    )
    builder.row(
        KeyboardButton(text="🔍 Найти депозиты пользователя"),
    )
    builder.row(
        KeyboardButton(text="⚙️ Управление уровнями"),
    )
    builder.row(
        KeyboardButton(text="📋 Pending депозиты"),
    )
    builder.row(
        KeyboardButton(text="💰 Коридоры доходности"),
    )
    builder.row(
        KeyboardButton(text="📈 ROI статистика"),
    )
    builder.row(
        KeyboardButton(text="◀️ Назад в админ-панель"),
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_deposit_levels_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin deposit levels selection keyboard.

    Returns:
        ReplyKeyboardMarkup with level selection buttons
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="Уровень 1"),
        KeyboardButton(text="Уровень 2"),
    )
    builder.row(
        KeyboardButton(text="Уровень 3"),
        KeyboardButton(text="Уровень 4"),
    )
    builder.row(
        KeyboardButton(text="Уровень 5"),
    )
    builder.row(
        KeyboardButton(text="🔢 Изм. макс. уровень"),
    )
    builder.row(
        KeyboardButton(text="◀️ Назад в админ-панель"),
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_deposit_level_actions_keyboard(
    level: int, is_active: bool
) -> ReplyKeyboardMarkup:
    """
    Admin deposit level actions keyboard.

    Args:
        level: Deposit level number (1-5)
        is_active: Whether level is currently active

    Returns:
        ReplyKeyboardMarkup with level action buttons
    """
    builder = ReplyKeyboardBuilder()

    # ROI Corridor management button (main feature)
    builder.row(
        KeyboardButton(text="💰 Настроить коридор доходности"),
    )

    # Enable/Disable level button
    if is_active:
        builder.row(
            KeyboardButton(text="❌ Отключить уровень"),
        )
    else:
        builder.row(
            KeyboardButton(text="✅ Включить уровень"),
        )

    # Back button
    builder.row(
        KeyboardButton(text="◀️ Назад к уровням"),
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def notification_settings_reply_keyboard(
    deposit_enabled: bool,
    withdrawal_enabled: bool,
    marketing_enabled: bool,
) -> ReplyKeyboardMarkup:
    """
    Notification settings reply keyboard.

    Args:
        deposit_enabled: Whether deposit notifications are enabled
        withdrawal_enabled: Whether withdrawal notifications are enabled
        marketing_enabled: Whether marketing notifications are enabled

    Returns:
        ReplyKeyboardMarkup with notification toggle buttons
    """
    builder = ReplyKeyboardBuilder()

    # Deposit notifications toggle
    deposit_text = (
        "✅ Уведомления о депозитах" if deposit_enabled
        else "❌ Уведомления о депозитах"
    )
    builder.row(
        KeyboardButton(text=deposit_text),
    )

    # Withdrawal notifications toggle
    withdrawal_text = (
        "✅ Уведомления о выводах" if withdrawal_enabled
        else "❌ Уведомления о выводах"
    )
    builder.row(
        KeyboardButton(text=withdrawal_text),
    )

    # Marketing notifications toggle
    marketing_text = (
        "✅ Маркетинговые уведомления" if marketing_enabled
        else "❌ Маркетинговые уведомления"
    )
    builder.row(
        KeyboardButton(text=marketing_text),
    )

    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def contacts_choice_keyboard() -> ReplyKeyboardMarkup:
    """
    Contacts choice keyboard for registration.

    Returns:
        ReplyKeyboardMarkup with contacts choice options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="✅ Да, оставить контакты"),
    )
    builder.row(
        KeyboardButton(text="⏭ Пропустить"),
    )

    return builder.as_markup(resize_keyboard=True)


def finpass_recovery_keyboard() -> ReplyKeyboardMarkup:
    """
    Financial password recovery keyboard.

    Returns:
        ReplyKeyboardMarkup with recovery options
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="❌ Отмена"),
    )
    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def transaction_history_keyboard(
    current_filter: str | None = None,
    has_prev: bool = False,
    has_next: bool = False,
) -> ReplyKeyboardMarkup:
    """
    Transaction history keyboard with filters and pagination.

    Args:
        current_filter: Current filter type (all/deposit/withdrawal/referral)
        has_prev: Whether there is a previous page
        has_next: Whether there is a next page

    Returns:
        ReplyKeyboardMarkup with filter and navigation options
    """
    builder = ReplyKeyboardBuilder()

    # Filter buttons
    builder.row(
        KeyboardButton(text="📊 Все транзакции"),
    )
    builder.row(
        KeyboardButton(text="💰 Депозиты"),
        KeyboardButton(text="💸 Выводы"),
    )
    builder.row(
        KeyboardButton(text="🎁 Реферальные"),
    )
    
    # Export button
    builder.row(
        KeyboardButton(text="📥 Скачать отчет (Excel)"),
    )

    # Navigation buttons
    nav_buttons = []
    if has_prev:
        nav_buttons.append(KeyboardButton(text="⬅ Предыдущая страница"))
    if has_next:
        nav_buttons.append(KeyboardButton(text="➡ Следующая страница"))
    
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def referral_list_keyboard(
    level: int = 1,
    page: int = 1,
    total_pages: int = 1,
) -> ReplyKeyboardMarkup:
    """
    Referral list keyboard with level selection and pagination.

    Args:
        level: Current referral level (1-3)
        page: Current page number
        total_pages: Total number of pages

    Returns:
        ReplyKeyboardMarkup with level selection and navigation options
    """
    builder = ReplyKeyboardBuilder()

    # Level selection buttons
    builder.row(
        KeyboardButton(text="📊 Уровень 1"),
        KeyboardButton(text="📊 Уровень 2"),
        KeyboardButton(text="📊 Уровень 3"),
    )

    # Navigation buttons (only if more than one page)
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(KeyboardButton(text="⬅ Предыдущая страница"))
        if page < total_pages:
            nav_buttons.append(KeyboardButton(text="➡ Следующая страница"))
        
        if nav_buttons:
            builder.row(*nav_buttons)

    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def withdrawal_history_keyboard(
    page: int = 1,
    total_pages: int = 1,
    has_withdrawals: bool = True,
) -> ReplyKeyboardMarkup:
    """
    Withdrawal history keyboard with pagination.

    Args:
        page: Current page number
        total_pages: Total number of pages
        has_withdrawals: Whether there are any withdrawals

    Returns:
        ReplyKeyboardMarkup with navigation options
    """
    builder = ReplyKeyboardBuilder()

    # Navigation buttons (only if more than one page and has withdrawals)
    if has_withdrawals and total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(KeyboardButton(text="⬅ Предыдущая страница выводов"))
        if page < total_pages:
            nav_buttons.append(KeyboardButton(text="➡ Следующая страница выводов"))
        
        if nav_buttons:
            builder.row(*nav_buttons)

    builder.row(
        KeyboardButton(text="📊 Главное меню"),
    )

    return builder.as_markup(resize_keyboard=True)


def master_key_management_reply_keyboard() -> ReplyKeyboardMarkup:
    """
    Master key management keyboard (reply).
    
    Returns:
        ReplyKeyboardMarkup with master key management options
    """
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🔍 Показать текущий ключ"))
    builder.row(KeyboardButton(text="🔄 Сгенерировать новый ключ"))
    builder.row(KeyboardButton(text="◀️ Главное меню"))
    return builder.as_markup(resize_keyboard=True)


def user_messages_navigation_keyboard(
    has_prev: bool,
    has_next: bool,
    is_super_admin: bool = False,
) -> ReplyKeyboardMarkup:
    """
    User messages navigation keyboard (reply).
    
    Args:
        has_prev: Whether there is a previous page
        has_next: Whether there is a next page
        is_super_admin: Whether user is super admin (shows delete button)
        
    Returns:
        ReplyKeyboardMarkup with navigation buttons
    """
    builder = ReplyKeyboardBuilder()
    
    # Navigation row
    nav_buttons = []
    if has_prev:
        nav_buttons.append(KeyboardButton(text=" Предыдущая страница"))
    if has_next:
        nav_buttons.append(KeyboardButton(text=" Следующая страница"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    # Delete button (only for super admin)
    if is_super_admin:
        builder.row(KeyboardButton(text=" Удалить все сообщения"))
    
    # Back button
    builder.row(KeyboardButton(text=" Назад в админ-панель"))
    
    return builder.as_markup(resize_keyboard=True)


def admin_roi_corridor_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    ROI corridor management menu keyboard.

    Returns:
        ReplyKeyboardMarkup with ROI corridor menu options
    """
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="⚙️ Настроить коридоры"))
    builder.row(KeyboardButton(text="💵 Настроить суммы уровней"))
    builder.row(KeyboardButton(text="📊 Текущие настройки"))
    builder.row(KeyboardButton(text="📜 История изменений"))
    builder.row(KeyboardButton(text="⏱ Настроить период начисления"))
    builder.row(KeyboardButton(text="◀️ Назад в управление депозитами"))
    builder.row(KeyboardButton(text="👑 Админ-панель"))
    return builder.as_markup(resize_keyboard=True)


def admin_roi_level_select_keyboard() -> ReplyKeyboardMarkup:
    """
    Level selection keyboard for ROI corridor management.

    Returns:
        ReplyKeyboardMarkup with level selection buttons
    """
    builder = ReplyKeyboardBuilder()
    for i in range(1, 6):
        builder.row(KeyboardButton(text=f"Уровень {i}"))
    builder.row(
        KeyboardButton(text="◀️ Отмена"),
        KeyboardButton(text="👑 Админ-панель"),
    )
    return builder.as_markup(resize_keyboard=True)


def admin_roi_mode_select_keyboard() -> ReplyKeyboardMarkup:
    """
    Mode selection keyboard for ROI corridor.

    Returns:
        ReplyKeyboardMarkup with mode selection buttons
    """
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🎲 Custom (случайный из коридора)"))
    builder.row(KeyboardButton(text="📊 Поровну (фиксированный для всех)"))
    builder.row(
        KeyboardButton(text="◀️ Отмена"),
        KeyboardButton(text="👑 Админ-панель"),
    )
    return builder.as_markup(resize_keyboard=True)


def admin_roi_applies_to_keyboard() -> ReplyKeyboardMarkup:
    """
    Application scope selection keyboard.

    Returns:
        ReplyKeyboardMarkup with application scope buttons
    """
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="⚡️ Применить к текущей сессии"))
    builder.row(KeyboardButton(text="⏭ Применить к следующей сессии"))
    builder.row(
        KeyboardButton(text="◀️ Отмена"),
        KeyboardButton(text="👑 Админ-панель"),
    )
    return builder.as_markup(resize_keyboard=True)


def admin_roi_confirmation_keyboard() -> ReplyKeyboardMarkup:
    """
    Confirmation keyboard for ROI corridor settings.

    Returns:
        ReplyKeyboardMarkup with confirmation buttons
    """
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="✅ Да, применить"))
    builder.row(KeyboardButton(text="❌ Нет, отменить"))
    return builder.as_markup(resize_keyboard=True)


def admin_ticket_list_keyboard(
    tickets: list,
    page: int = 1,
    total_pages: int = 1,
) -> ReplyKeyboardMarkup:
    """
    Keyboard with ticket buttons for admin selection.

    Args:
        tickets: List of SupportTicket objects
        page: Current page
        total_pages: Total pages

    Returns:
        ReplyKeyboardMarkup with ticket buttons
    """
    builder = ReplyKeyboardBuilder()

    # Ticket buttons (2 per row)
    for i in range(0, len(tickets), 2):
        row_buttons = []
        # Button 1
        t1 = tickets[i]
        user_label1 = f"ID: {t1.user_id}"
        if t1.user and t1.user.username:
            user_label1 = f"@{t1.user.username}"
        row_buttons.append(KeyboardButton(text=f"🎫 #{t1.id} {user_label1}"))
        
        # Button 2 (if exists)
        if i + 1 < len(tickets):
            t2 = tickets[i+1]
            user_label2 = f"ID: {t2.user_id}"
            if t2.user and t2.user.username:
                user_label2 = f"@{t2.user.username}"
            row_buttons.append(KeyboardButton(text=f"🎫 #{t2.id} {user_label2}"))
            
        builder.row(*row_buttons)

    # Navigation
    nav_buttons = []
    if total_pages > 1:
        if page > 1:
            nav_buttons.append(KeyboardButton(text="⬅ Предыдущая"))
        if page < total_pages:
            nav_buttons.append(KeyboardButton(text="Следующая ➡"))
    
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        KeyboardButton(text="🆘 Техподдержка"),
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_user_list_keyboard(
    users: list,
    page: int = 1,
    total_pages: int = 1,
) -> ReplyKeyboardMarkup:
    """
    Keyboard with user buttons for admin selection.

    Args:
        users: List of User objects
        page: Current page
        total_pages: Total pages

    Returns:
        ReplyKeyboardMarkup with user buttons
    """
    builder = ReplyKeyboardBuilder()

    # User buttons (2 per row)
    for i in range(0, len(users), 2):
        row_buttons = []
        u1 = users[i]
        label1 = f"@{u1.username}" if u1.username else f"ID {u1.telegram_id}"
        # Button text format: "🆔 {id}: {label}" to easily parse ID later
        row_buttons.append(KeyboardButton(text=f"🆔 {u1.id}: {label1}"))
        
        if i + 1 < len(users):
            u2 = users[i+1]
            label2 = f"@{u2.username}" if u2.username else f"ID {u2.telegram_id}"
            row_buttons.append(KeyboardButton(text=f"🆔 {u2.id}: {label2}"))
            
        builder.row(*row_buttons)

    # Navigation
    nav_buttons = []
    if total_pages > 1:
        if page > 1:
            nav_buttons.append(KeyboardButton(text="⬅ Предыдущая"))
        if page < total_pages:
            nav_buttons.append(KeyboardButton(text="Следующая ➡"))
    
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        KeyboardButton(text="👥 Управление пользователями"),
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_user_profile_keyboard(user_is_blocked: bool) -> ReplyKeyboardMarkup:
    """
    Keyboard for managing a specific user.

    Args:
        user_is_blocked: Whether the user is currently blocked

    Returns:
        ReplyKeyboardMarkup with user profile actions
    """
    builder = ReplyKeyboardBuilder()
    
    block_text = "✅ Разблокировать" if user_is_blocked else "🚫 Заблокировать"
    
    builder.row(
        KeyboardButton(text="💳 Изменить баланс"),
        KeyboardButton(text=block_text),
    )
    builder.row(
        KeyboardButton(text="📜 История транзакций"),
        KeyboardButton(text="👥 Рефералы"),
    )
    builder.row(
        KeyboardButton(text="⚠️ Терминировать аккаунт"),
    )
    builder.row(
        KeyboardButton(text="◀️ К списку пользователей"),
        KeyboardButton(text="👑 Админ-панель"),
    )
    return builder.as_markup(resize_keyboard=True)


def admin_finpass_request_list_keyboard(
    requests: list,
    page: int = 1,
    total_pages: int = 1,
) -> ReplyKeyboardMarkup:
    """
    Keyboard with finpass recovery request buttons for admin selection.

    Args:
        requests: List of FinpassRecoveryRequest objects
        page: Current page
        total_pages: Total pages

    Returns:
        ReplyKeyboardMarkup with request buttons
    """
    builder = ReplyKeyboardBuilder()

    # Request buttons (2 per row)
    for i in range(0, len(requests), 2):
        row_buttons = []
        # Button 1
        r1 = requests[i]
        # Try to get user label if available (joined) or just ID
        user_label1 = f"User {r1.user_id}"
        if hasattr(r1, 'user') and r1.user:
             if r1.user.username:
                 user_label1 = f"@{r1.user.username}"
             elif r1.user.telegram_id:
                 user_label1 = f"TG {r1.user.telegram_id}"
        
        row_buttons.append(KeyboardButton(text=f"🔑 Запрос #{r1.id} {user_label1}"))
        
        # Button 2 (if exists)
        if i + 1 < len(requests):
            r2 = requests[i+1]
            user_label2 = f"User {r2.user_id}"
            if hasattr(r2, 'user') and r2.user:
                 if r2.user.username:
                     user_label2 = f"@{r2.user.username}"
                 elif r2.user.telegram_id:
                     user_label2 = f"TG {r2.user.telegram_id}"
            row_buttons.append(KeyboardButton(text=f"🔑 Запрос #{r2.id} {user_label2}"))
            
        builder.row(*row_buttons)

    # Navigation
    nav_buttons = []
    if total_pages > 1:
        if page > 1:
            nav_buttons.append(KeyboardButton(text="⬅ Предыдущая"))
        if page < total_pages:
            nav_buttons.append(KeyboardButton(text="Следующая ➡"))
    
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        KeyboardButton(text="👑 Админ-панель"),
    )

    return builder.as_markup(resize_keyboard=True)


def admin_finpass_request_actions_keyboard() -> ReplyKeyboardMarkup:
    """
    Actions keyboard for a specific finpass recovery request.

    Returns:
        ReplyKeyboardMarkup with actions
    """
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="✅ Одобрить запрос"),
        KeyboardButton(text="❌ Отклонить запрос"),
    )
    builder.row(
        KeyboardButton(text="◀️ Назад к списку"),
        KeyboardButton(text="👑 Админ-панель"),
    )
    return builder.as_markup(resize_keyboard=True)


def admin_financial_list_keyboard(
    users: list,
    page: int = 1,
    total_pages: int = 1,
) -> ReplyKeyboardMarkup:
    """
    Keyboard with users for financial report selection.

    Args:
        users: List of UserFinancialDTO objects
        page: Current page
        total_pages: Total pages

    Returns:
        ReplyKeyboardMarkup
    """
    builder = ReplyKeyboardBuilder()

    for user in users:
        # Truncate if too long, but try to show financial summary
        username = user.username or str(user.telegram_id)
        if len(username) > 15:
            username = username[:12] + "..."
            
        text = f"👤 {user.id}. {username} | +{int(user.total_deposited)} | -{int(user.total_withdrawn)}"
        builder.row(KeyboardButton(text=text))

    # Navigation
    nav_buttons = []
    if total_pages > 1:
        if page > 1:
            nav_buttons.append(KeyboardButton(text="⬅ Предыдущая"))
        if page < total_pages:
            nav_buttons.append(KeyboardButton(text="Следующая ➡"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(KeyboardButton(text="👑 Админ-панель"))

    return builder.as_markup(resize_keyboard=True)


def admin_user_financial_keyboard() -> ReplyKeyboardMarkup:
    """
    Actions for a selected user in financial report.

    Returns:
        ReplyKeyboardMarkup
    """
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="💸 История выводов"),
        KeyboardButton(text="📜 История начислений"),
    )
    builder.row(
        KeyboardButton(text="◀️ Назад к списку"),
        KeyboardButton(text="👑 Админ-панель"),
    )
    return builder.as_markup(resize_keyboard=True)


def admin_back_keyboard() -> ReplyKeyboardMarkup:
    """
    Simple back keyboard.

    Returns:
        ReplyKeyboardMarkup
    """
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="◀️ Назад"))
    builder.row(KeyboardButton(text="👑 Админ-панель"))
    return builder.as_markup(resize_keyboard=True)


def admin_user_financial_detail_keyboard() -> ReplyKeyboardMarkup:
    """
    Keyboard for detailed user financial card.
    
    Returns:
        ReplyKeyboardMarkup with navigation options
    """
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📊 Все депозиты"))
    builder.row(KeyboardButton(text="💸 Все выводы"))
    builder.row(KeyboardButton(text="💳 История кошельков"))
    builder.row(
        KeyboardButton(text="⬅ Назад к списку"),
        KeyboardButton(text="👑 Админ-панель")
    )
    return builder.as_markup(resize_keyboard=True)


def admin_deposits_list_keyboard(
    page: int = 1, total_pages: int = 1
) -> ReplyKeyboardMarkup:
    """
    Keyboard for deposits list with pagination.
    
    Args:
        page: Current page number
        total_pages: Total number of pages
        
    Returns:
        ReplyKeyboardMarkup with pagination
    """
    builder = ReplyKeyboardBuilder()
    
    # Navigation
    nav_buttons = []
    if total_pages > 1:
        if page > 1:
            nav_buttons.append(KeyboardButton(text="⬅ Предыдущая"))
        if page < total_pages:
            nav_buttons.append(KeyboardButton(text="Следующая ➡"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        KeyboardButton(text="◀️ К карточке"),
        KeyboardButton(text="👑 Админ-панель")
    )
    
    return builder.as_markup(resize_keyboard=True)


def admin_withdrawals_list_keyboard(
    page: int = 1, total_pages: int = 1
) -> ReplyKeyboardMarkup:
    """
    Keyboard for withdrawals list with pagination.
    
    Args:
        page: Current page number
        total_pages: Total number of pages
        
    Returns:
        ReplyKeyboardMarkup with pagination
    """
    builder = ReplyKeyboardBuilder()
    
    # Navigation
    nav_buttons = []
    if total_pages > 1:
        if page > 1:
            nav_buttons.append(KeyboardButton(text="⬅ Предыдущая"))
        if page < total_pages:
            nav_buttons.append(KeyboardButton(text="Следующая ➡"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        KeyboardButton(text="◀️ К карточке"),
        KeyboardButton(text="👑 Админ-панель")
    )
    
    return builder.as_markup(resize_keyboard=True)


def admin_wallet_history_keyboard() -> ReplyKeyboardMarkup:
    """
    Keyboard for wallet change history.
    
    Returns:
        ReplyKeyboardMarkup with back navigation
    """
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="◀️ К карточке"),
        KeyboardButton(text="👑 Админ-панель")
    )
    return builder.as_markup(resize_keyboard=True)