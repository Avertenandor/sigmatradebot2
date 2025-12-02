"""
Menu buttons constants.

Centralized list of menu button texts to prevent handlers from intercepting
    them.
"""

# Main menu buttons
MAIN_MENU_BUTTONS = [
    "💰 Депозит",
    "💸 Вывод",
    "📦 Мои депозиты",
    "👥 Рефералы",
    "📊 Баланс",
    "💬 Поддержка",
    "⚙️ Настройки",
    "📖 Инструкции",
    "📜 История",
    "✅ Пройти верификацию",
    "🔑 Восстановить финпароль",
    "📝 Подать апелляцию",
    "📝 Регистрация",
    "📊 Главное меню",
    "👑 Админ-панель",
    "📊 Калькулятор",  # ROI Calculator
    "📋 Сравнить все уровни",  # Calculator comparison
]

# Deposit menu buttons
DEPOSIT_MENU_BUTTONS = [
    "💰 Пополнить Level 1 (10 USDT)",
    "💰 Пополнить Level 2 (50 USDT)",
    "💰 Пополнить Level 3 (100 USDT)",
    "💰 Пополнить Level 4 (150 USDT)",
    "💰 Пополнить Level 5 (300 USDT)",
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
# NOTE:
# 1) Этот список должен соответствовать раскладке admin_keyboard() в
#    bot/keyboards/reply.py, чтобы is_menu_button() корректно распознавал
#    все кнопки админ-панели.
# 2) Тексты должны совпадать с handler-условиями F.text == "...".
ADMIN_MENU_BUTTONS = [
    "📊 Статистика",
    "👥 Управление пользователями",
    "💸 Заявки на вывод",
    "📢 Рассылка",
    "🆘 Техподдержка",
    "🔐 Управление кошельком",
    "📡 Блокчейн Настройки",
    "🚫 Управление черным списком",
    "🔑 Восстановление пароля",
    "💰 Управление депозитами",
    "🚨 Аварийные стопы",
    "📝 Просмотр сообщений пользователей",
    "💰 Финансовая отчётность",
    "👥 Управление админами",  # Only for super_admin
    "🔑 Управление мастер-ключом",  # Only for super_admin (restricted in handlers)
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

# Navigation buttons (used across multiple menus)
NAVIGATION_BUTTONS = [
    "⬅ Назад",
    "◀️ Главное меню",
    "👑 Админ-панель",
    "⏭ Пропустить",  # Registration skip button (may have leftover keyboard)
    "⏭️ Пропустить",  # Same with FE0F variation selector
    "✅ Да, оставить контакты",  # Registration contacts button
    # Note: "📊 Статистика" is also in ADMIN_MENU_BUTTONS, but included here
    # for completeness as it's used in navigation contexts
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
    # CONFIRMATION_BUTTONS should NOT clear state as they are used within FSM flows
    # + CONFIRMATION_BUTTONS
    + NAVIGATION_BUTTONS
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
