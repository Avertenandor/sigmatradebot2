"""
Admin Panel Handler
Handles admin panel main menu and platform statistics
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService
from app.services.deposit_service import DepositService
from app.services.referral_service import ReferralService
from bot.utils.formatters import format_usdt


router = Router(name="admin_panel")


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Get admin panel main menu keyboard"""
    buttons = [
        [
            InlineKeyboardButton(
                text="📊 Статистика", callback_data="admin_stats"
            ),
        ],
        [
            InlineKeyboardButton(
                text="👥 Управление пользователями",
                callback_data="admin_users",
            ),
        ],
        [
            InlineKeyboardButton(
                text="💸 Заявки на вывод",
                callback_data="admin_pending_withdrawals",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📢 Рассылка", callback_data="admin_broadcast"
            ),
            InlineKeyboardButton(
                text="🆘 Техподдержка", callback_data="admin_support"
            ),
        ],
        [
            InlineKeyboardButton(
                text="◀️ Главное меню", callback_data="main_menu"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_stats_keyboard(range_type: str = "all") -> InlineKeyboardMarkup:
    """Get admin statistics keyboard"""
    buttons = [
        [
            InlineKeyboardButton(
                text="◀️ Админ-панель", callback_data="admin_panel"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "admin_panel")
async def handle_admin_panel(
    callback: CallbackQuery,
    session: AsyncSession,
    is_admin: bool = False,
) -> None:
    """Handle admin panel main menu"""
    if not is_admin:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return

    message = """
👑 **Панель администратора**

Добро пожаловать в панель управления SigmaTrade Bot.

Выберите действие:
    """.strip()

    await callback.message.edit_text(
        message,
        parse_mode="Markdown",
        reply_markup=get_admin_panel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_stats"))
async def handle_admin_stats(
    callback: CallbackQuery,
    session: AsyncSession,
    is_admin: bool = False,
) -> None:
    """Handle platform statistics"""
    if not is_admin:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return

    user_service = UserService(session)
    deposit_service = DepositService(session)
    referral_service = ReferralService(session)

    # Get range from callback data
    range_type = "all"
    if "_" in callback.data:
        range_type = callback.data.split("_")[-1]

    # Get statistics
    total_users = await user_service.get_total_users()
    verified_users = await user_service.get_verified_users()
    deposit_stats = await deposit_service.get_platform_stats()
    referral_stats = await referral_service.get_platform_referral_stats()

    message = f"""
📊 **Статистика платформы**

**Пользователи:**
👥 Всего: {total_users}
✅ Верифицированы: {verified_users}
❌ Не верифицированы: {total_users - verified_users}

**Депозиты:**
💰 Всего депозитов: {deposit_stats['total_deposits']}
💵 Общая сумма: {format_usdt(deposit_stats['total_amount'])} USDT
👤 Пользователей с депозитами: {deposit_stats['total_users']}

**По уровням:**
• Уровень 1: {deposit_stats['deposits_by_level'].get(1, 0)} депозитов
• Уровень 2: {deposit_stats['deposits_by_level'].get(2, 0)} депозитов
• Уровень 3: {deposit_stats['deposits_by_level'].get(3, 0)} депозитов
• Уровень 4: {deposit_stats['deposits_by_level'].get(4, 0)} депозитов
• Уровень 5: {deposit_stats['deposits_by_level'].get(5, 0)} депозитов

**Рефералы:**
🤝 Всего связей: {referral_stats['total_referrals']}
💰 Всего начислено: {format_usdt(referral_stats['total_earnings'])} USDT
✅ Выплачено: {format_usdt(referral_stats['paid_earnings'])} USDT
⏳ Ожидает выплаты: {format_usdt(referral_stats['pending_earnings'])} USDT

**По уровням:**
• Уровень 1: {referral_stats['by_level'].get(1, {}).get('count', 0)} ({format_usdt(referral_stats['by_level'].get(1, {}).get('earnings', 0))} USDT)
• Уровень 2: {referral_stats['by_level'].get(2, {}).get('count', 0)} ({format_usdt(referral_stats['by_level'].get(2, {}).get('earnings', 0))} USDT)
• Уровень 3: {referral_stats['by_level'].get(3, {}).get('count', 0)} ({format_usdt(referral_stats['by_level'].get(3, {}).get('earnings', 0))} USDT)
    """.strip()

    await callback.message.edit_text(
        message,
        parse_mode="Markdown",
        reply_markup=get_admin_stats_keyboard(range_type),
    )
    await callback.answer()
