"""
Profile Handler
Handles user profile display with stats and balance
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService
from app.services.deposit_service import DepositService
from bot.utils.formatters import format_usdt


router = Router(name="profile")


def create_progress_bar(percent: float, length: int = 10) -> str:
    """Create a visual progress bar"""
    filled = round((percent / 100) * length)
    empty = length - filled
    return "█" * filled + "░" * empty


@router.callback_query(F.data == "profile")
async def handle_profile(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
) -> None:
    """Handle profile view"""
    user_service = UserService(session)
    deposit_service = DepositService(session)

    # Get user
    user = await user_service.get_by_id(user_id)
    if not user:
        await callback.answer("Пользователь не найден")
        return

    # Get user stats
    stats = await user_service.get_user_stats(user_id)

    # Get user balance
    balance = await user_service.get_user_balance(user_id)

    # Get ROI progress for level 1
    roi_progress = await deposit_service.get_level1_roi_progress(user_id)

    # Get bot username for referral link
    bot = callback.bot
    bot_info = await bot.get_me()
    referral_link = user_service.generate_referral_link(
        user.id, bot_info.username
    )

    # Build ROI section
    roi_section = ""
    if roi_progress.get("has_active_deposit") and not roi_progress.get(
        "is_completed"
    ):
        progress_bar = create_progress_bar(
            roi_progress.get("roi_percent", 0)
        )
        roi_section = f"""
**🎯 ROI Прогресс (Уровень 1):**
💵 Депозит: {format_usdt(roi_progress.get('deposit_amount', 0))} USDT
📊 Прогресс: {progress_bar} {roi_progress.get('roi_percent', 0):.1f}%
✅ Получено: {format_usdt(roi_progress.get('roi_paid', 0))} USDT
⏳ Осталось: {format_usdt(roi_progress.get('roi_remaining', 0))} USDT
🎯 Цель: {format_usdt(roi_progress.get('roi_cap', 0))} USDT (500%)

"""
    elif roi_progress.get("has_active_deposit") and roi_progress.get(
        "is_completed"
    ):
        roi_section = f"""
**🎯 ROI Завершён (Уровень 1):**
✅ Достигнут максимум 500%!
💰 Получено: {format_usdt(roi_progress.get('roi_paid', 0))} USDT
📌 Создайте новый депозит 10 USDT чтобы продолжить

"""

    # Format wallet address
    wallet_display = user.wallet_address
    if len(user.wallet_address) > 20:
        wallet_display = (
            f"{user.wallet_address[:10]}...{user.wallet_address[-8:]}"
        )

    # Build profile message
    message = f"""
👤 **Ваш профиль**

**Основная информация:**
🆔 ID: `{user.id}`
👤 Username: {f"@{user.username}" if user.username else "Не указан"}
💳 Кошелек: `{user.wallet_address}`
{f"({wallet_display})" if len(user.wallet_address) > 20 else ""}

**Статус:**
{"✅" if user.is_verified else "❌"} Верификация: {"Пройдена" if user.is_verified else "Не пройдена"}
{"🚫 Аккаунт заблокирован" if user.is_banned else "✅ Аккаунт активен"}

**Баланс:**
💰 Доступно для вывода: **{format_usdt(balance.get('available_balance', 0))} USDT**
💸 Всего заработано: {format_usdt(balance.get('total_earned', 0))} USDT
⏳ В ожидании выплаты: {format_usdt(balance.get('pending_earnings', 0))} USDT
{f"🔒 Заблокировано в выводах: {format_usdt(balance.get('pending_withdrawals', 0))} USDT" if balance.get('pending_withdrawals', 0) > 0 else ""}
✅ Уже выплачено: {format_usdt(balance.get('total_paid', 0))} USDT

{roi_section}**Депозиты и рефералы:**
💰 Всего депозитов: {format_usdt(stats.get('total_deposits', 0))} USDT
👥 Рефералов: {stats.get('referral_count', 0)}
📊 Активных уровней: {len(stats.get('activated_levels', []))}/5

{f"**Контакты:**" if user.phone or user.email else ""}
{f"📞 {user.phone}" if user.phone else ""}
{f"📧 {user.email}" if user.email else ""}

**Реферальная ссылка:**
`{referral_link}`

📅 Дата регистрации: {user.created_at.strftime("%d.%m.%Y")}
    """.strip()

    # Create keyboard
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Главное меню", callback_data="main_menu"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        message, parse_mode="Markdown", reply_markup=keyboard
    )
    await callback.answer()
