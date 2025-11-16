"""
Menu buttons constants.

Centralized list of menu button texts to prevent handlers from intercepting them.
"""

# Main menu buttons
MAIN_MENU_BUTTONS = [
    "💰 Депозит",
    "💸 Вывод",
    "👥 Рефералы",
    "📊 Баланс",
    "💬 Поддержка",
    "⚙️ Настройки",
    "✅ Пройти верификацию",
    "📝 Подать апелляцию",
    "📊 Главное меню",
    "👑 Админ-панель",
]

# Deposit menu buttons
DEPOSIT_MENU_BUTTONS = [
    "💰 Пополнить Level 1 (50 USDT)",
    "💰 Пополнить Level 2 (100 USDT)",
    "💰 Пополнить Level 3 (250 USDT)",
    "💰 Пополнить Level 4 (500 USDT)",
    "💰 Пополнить Level 5 (1000 USDT)",
]

# Withdrawal menu buttons
WITHDRAWAL_MENU_BUTTONS = [
    "💸 Вывести всю сумму",
    "💵 Вывести указанную сумму",
    "📜 История выводов",
]

# Referral menu buttons
REFERRAL_MENU_BUTTONS = [
    "👥 Мои рефералы",
    "💰 Мой заработок",
    "📊 Статистика рефералов",
]

# Settings menu buttons
SETTINGS_MENU_BUTTONS = [
    "👤 Мой профиль",
    "💳 Мой кошелек",
    "🔔 Настройки уведомлений",
    "📝 Обновить контакты",
]

# Support menu buttons
SUPPORT_MENU_BUTTONS = [
    "✉️ Создать обращение",
    "📋 Мои обращения",
    "❓ FAQ",
]

# Admin menu buttons
ADMIN_MENU_BUTTONS = [
    "👥 Управление пользователями",
    "💸 Управление выводами",
    "📊 Статистика бота",
    "📢 Рассылка",
    "⚙️ Настройки депозитов",
    "🔑 Настройки кошелька",
    "🚫 Управление blacklist",
]

# Admin users menu buttons
ADMIN_USERS_MENU_BUTTONS = [
    "🔍 Найти пользователя",
    "👥 Список пользователей",
    "🚫 Заблокировать пользователя",
    "⚠️ Терминировать аккаунт",
]

# Admin withdrawals menu buttons
ADMIN_WITHDRAWALS_MENU_BUTTONS = [
    "⏳ Ожидающие выводы",
    "✅ Одобренные выводы",
    "❌ Отклоненные выводы",
]

# Confirmation buttons
CONFIRMATION_BUTTONS = [
    "✅ Да",
    "❌ Нет",
    "❌ Отмена",
]

# All menu buttons
ALL_MENU_BUTTONS = (
    MAIN_MENU_BUTTONS
    + DEPOSIT_MENU_BUTTONS
    + WITHDRAWAL_MENU_BUTTONS
    + REFERRAL_MENU_BUTTONS
    + SETTINGS_MENU_BUTTONS
    + SUPPORT_MENU_BUTTONS
    + ADMIN_MENU_BUTTONS
    + ADMIN_USERS_MENU_BUTTONS
    + ADMIN_WITHDRAWALS_MENU_BUTTONS
    + CONFIRMATION_BUTTONS
)


def is_menu_button(text: str) -> bool:
    """
    Check if text is a menu button.
    
    Args:
        text: Message text to check
        
    Returns:
        True if text is a menu button, False otherwise
    """
    return text in ALL_MENU_BUTTONS

