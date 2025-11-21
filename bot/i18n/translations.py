"""
Translation strings for all supported languages.

R13-3: Multi-language support for the bot.
"""

# Russian translations (default)
RU_TRANSLATIONS = {
    "menu": {
        "main": "📊 *Главное меню*\n\nВыберите действие:",
        "deposit": "💰 Депозит",
        "withdrawal": "💸 Вывод",
        "balance": "📊 Баланс",
        "referrals": "👥 Рефералы",
        "settings": "⚙️ Настройки",
        "support": "💬 Поддержка",
        "instructions": "📖 Инструкции",
        "history": "📜 История",
        "verification": "✅ Пройти верификацию",
        "finpass_recovery": "🔑 Восстановить финпароль",
        "appeal": "📝 Подать апелляцию",
    },
    "settings": {
        "title": "⚙️ *Настройки*\n\nВыберите действие:",
        "profile": "👤 Мой профиль",
        "wallet": "💳 Мой кошелек",
        "notifications": "🔔 Настройки уведомлений",
        "contacts": "📝 Обновить контакты",
        "language": "🌐 Изменить язык",
    },
    "language": {
        "title": "🌐 *Выбор языка*\n\nВыберите язык:",
        "changed": "✅ Язык изменён на {language}",
        "error": "❌ Ошибка при изменении языка",
    },
    "common": {
        "back": "◀️ Назад",
        "cancel": "❌ Отмена",
        "confirm": "✅ Подтвердить",
        "error": "⚠️ Произошла ошибка. Попробуйте позже.",
        "not_registered": "❌ Пожалуйста, сначала зарегистрируйтесь",
        "welcome_back": "Добро пожаловать обратно, {username}!",
        "your_balance": "Ваш баланс: {balance} USDT",
        "use_menu": "Используйте меню ниже для навигации.",
        "choose_action": "Выберите действие ниже:",
        "welcome": "👋 Добро пожаловать обратно!",
        "user": "пользователь",
        "welcome_user": "Добро пожаловать, {username}!",
    },
    "errors": {
        "database_unavailable": (
            "⚠️ Технические работы, сервис временно недоступен.\n\n"
            "Ваши средства в безопасности, все операции будут "
            "обработаны после восстановления.\n\n"
            "Попробуйте через 5-10 минут."
        ),
        "database_connection_failed": (
            "⚠️ Проблема с подключением к базе данных.\n\n"
            "Ваши средства в безопасности. "
            "Попробуйте позже или обратитесь в поддержку."
        ),
        "database_operational_error": (
            "⚠️ Временная недоступность базы данных.\n\n"
            "Ваши средства в безопасности. "
            "Все операции будут обработаны после восстановления.\n\n"
            "Попробуйте через несколько минут."
        ),
        "database_interface_error": (
            "⚠️ Проблема с подключением к базе данных.\n\n"
            "Ваши средства в безопасности. "
            "Попробуйте позже или обратитесь в поддержку."
        ),
        "database_general_error": (
            "⚠️ Ошибка базы данных.\n\n"
            "Ваши средства в безопасности. "
            "Попробуйте позже или обратитесь в поддержку."
        ),
        "system_error": (
            "⚠️ Системная ошибка.\n\n"
            "Попробуйте позже или обратитесь в поддержку."
        ),
    },
}

# English translations
EN_TRANSLATIONS = {
    "menu": {
        "main": "📊 *Main Menu*\n\nChoose an action:",
        "deposit": "💰 Deposit",
        "withdrawal": "💸 Withdrawal",
        "balance": "📊 Balance",
        "referrals": "👥 Referrals",
        "settings": "⚙️ Settings",
        "support": "💬 Support",
        "instructions": "📖 Instructions",
        "history": "📜 History",
        "verification": "✅ Verify",
        "finpass_recovery": "🔑 Recover Financial Password",
        "appeal": "📝 Submit Appeal",
    },
    "settings": {
        "title": "⚙️ *Settings*\n\nChoose an action:",
        "profile": "👤 My Profile",
        "wallet": "💳 My Wallet",
        "notifications": "🔔 Notification Settings",
        "contacts": "📝 Update Contacts",
        "language": "🌐 Change Language",
    },
    "language": {
        "title": "🌐 *Language Selection*\n\nChoose a language:",
        "changed": "✅ Language changed to {language}",
        "error": "❌ Error changing language",
    },
    "common": {
        "back": "◀️ Back",
        "cancel": "❌ Cancel",
        "confirm": "✅ Confirm",
        "error": "⚠️ An error occurred. Please try again later.",
        "not_registered": "❌ Please register first",
        "welcome_back": "Welcome back, {username}!",
        "your_balance": "Your balance: {balance} USDT",
        "use_menu": "Use the menu below to navigate.",
        "choose_action": "Choose an action below:",
        "welcome": "👋 Welcome back!",
        "user": "user",
        "welcome_user": "Welcome, {username}!",
    },
    "errors": {
        "database_unavailable": (
            "⚠️ Technical maintenance, service temporarily unavailable.\n\n"
            "Your funds are safe, all operations will be "
            "processed after restoration.\n\n"
            "Please try again in 5-10 minutes."
        ),
        "database_connection_failed": (
            "⚠️ Database connection problem.\n\n"
            "Your funds are safe. "
            "Please try again later or contact support."
        ),
        "database_operational_error": (
            "⚠️ Database temporarily unavailable.\n\n"
            "Your funds are safe. "
            "All operations will be processed after restoration.\n\n"
            "Please try again in a few minutes."
        ),
        "database_interface_error": (
            "⚠️ Database connection problem.\n\n"
            "Your funds are safe. "
            "Please try again later or contact support."
        ),
        "database_general_error": (
            "⚠️ Database error.\n\n"
            "Your funds are safe. "
            "Please try again later or contact support."
        ),
        "system_error": (
            "⚠️ System error.\n\n"
            "Please try again later or contact support."
        ),
    },
}

# All translations
TRANSLATIONS = {
    "ru": RU_TRANSLATIONS,
    "en": EN_TRANSLATIONS,
}

