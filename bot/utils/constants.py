"""
Bot Constants
Common constants used across bot handlers
"""

# Referral commission rates by level
REFERRAL_RATES = {
    1: 0.03,  # 3% for level 1 (direct referrals)
    2: 0.02,  # 2% for level 2
    3: 0.05,  # 5% for level 3
}

# Deposit levels configuration
DEPOSIT_LEVELS = {
    1: 10.0,     # 10 USDT
    2: 50.0,     # 50 USDT
    3: 100.0,    # 100 USDT
    4: 500.0,    # 500 USDT
    5: 1000.0,   # 1000 USDT
}

# ROI cap for level 1 deposits
ROI_CAP_MULTIPLIER = 5.0  # 500% (5x)

# Error messages
ERROR_MESSAGES = {
    "NOT_REGISTERED": "❌ Пожалуйста, сначала зарегистрируйтесь",
    "ADMIN_ONLY": "❌ Эта функция доступна только администраторам",
    "INSUFFICIENT_BALANCE": "❌ Недостаточно средств на балансе",
    "INVALID_WALLET": "❌ Неверный адрес кошелька",
    "INVALID_AMOUNT": "❌ Неверная сумма",
    "USER_BANNED": "❌ Ваш аккаунт заблокирован",
}

# Button labels
BUTTON_LABELS = {
    "MAIN_MENU": "🏠 Главное меню",
    "BACK": "◀️ Назад",
    "CANCEL": "❌ Отмена",
    "CONFIRM": "✅ Подтвердить",
}

# Admin broadcast cooldown (15 minutes)
BROADCAST_COOLDOWN_MS = 15 * 60 * 1000
