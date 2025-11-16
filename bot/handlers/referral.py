"""
Referral Handler - ТОЛЬКО REPLY KEYBOARDS!

Handles referral program actions including stats, leaderboard, and earnings.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.referral_service import ReferralService
from app.services.user_service import UserService
from bot.keyboards.reply import referral_keyboard, main_menu_reply_keyboard
from bot.utils.constants import REFERRAL_RATES
from bot.utils.formatters import format_usdt
from bot.utils.menu_buttons import is_menu_button

router = Router(name="referral")


@router.message(F.text == "👥 Мои рефералы")
async def handle_my_referrals(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    """Show user's referrals list."""
    referral_service = ReferralService(session)
    
    # Get referral stats
    stats = await referral_service.get_referral_stats(user.id)
    
    text = (
        f"👥 *Мои рефералы*\n\n"
        f"*Статистика:*\n"
        f"👥 Прямые партнеры (Уровень 1): *{stats['direct_referrals']}*\n"
        f"👥 Уровень 2: *{stats['level2_referrals']}*\n"
        f"👥 Уровень 3: *{stats['level3_referrals']}*\n\n"
        f"*Комиссии:*\n"
        f"• Уровень 1: {REFERRAL_RATES[1] * 100}% от депозитов прямых партнеров\n"
        f"• Уровень 2: {REFERRAL_RATES[2] * 100}% от партнеров второго уровня\n"
        f"• Уровень 3: {REFERRAL_RATES[3] * 100}% от партнеров третьего уровня\n\n"
        f"📈 Чем больше ваша сеть, тем больше доход!"
    )
    
    await message.answer(text, parse_mode="Markdown", reply_markup=referral_keyboard())


@router.message(F.text == "💰 Мой заработок")
async def handle_my_earnings(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    """Show user's referral earnings."""
    referral_service = ReferralService(session)
    
    # Get referral stats
    stats = await referral_service.get_referral_stats(user.id)
    
    # Get pending earnings
    result = await referral_service.get_pending_earnings(user.id, page=1, limit=10)
    earnings = result["earnings"]
    total_amount = result["total_amount"]
    
    text = (
        f"💰 *Мой заработок*\n\n"
        f"*Доходы:*\n"
        f"💵 Всего заработано: *{format_usdt(stats['total_earned'])} USDT*\n"
        f"⏳ Ожидает выплаты: *{format_usdt(stats['pending_earnings'])} USDT*\n"
        f"✅ Выплачено: *{format_usdt(stats['paid_earnings'])} USDT*\n\n"
    )
    
    if earnings:
        text += f"*Последние выплаты:*\n"
        for earning in earnings[:5]:
            date = earning["created_at"].strftime("%d.%m.%Y")
            emoji = "✅" if earning["paid"] else "⏳"
            text += (
                f"{emoji} {format_usdt(earning['amount'])} USDT\n"
                f"   Дата: {date}\n"
                f"   Статус: {'Выплачено' if earning['paid'] else 'Ожидает'}\n\n"
            )
        
        if total_amount > 0:
            text += f"💰 Всего ожидает: *{format_usdt(total_amount)} USDT*\n"
    else:
        text += "У вас пока нет ожидающих выплат."
    
    await message.answer(text, parse_mode="Markdown", reply_markup=referral_keyboard())


@router.message(F.text == "📊 Статистика рефералов")
async def handle_referral_stats(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    """Show comprehensive referral statistics."""
    referral_service = ReferralService(session)
    user_service = UserService(session)
    
    # Get referral stats
    stats = await referral_service.get_referral_stats(user.id)
    
    # Get bot info for referral link
    from app.config.settings import settings
    bot_username = settings.telegram_bot_username
    referral_link = user_service.generate_referral_link(user.id, bot_username)
    
    # Get user position in leaderboard
    user_position = await referral_service.get_user_leaderboard_position(user.id)
    
    text = (
        f"📊 *Статистика рефералов*\n\n"
        f"*Ваша реферальная ссылка:*\n"
        f"`{referral_link}`\n\n"
        f"*Статистика:*\n"
        f"👥 Прямые партнеры: *{stats['direct_referrals']}*\n"
        f"👥 Уровень 2: *{stats['level2_referrals']}*\n"
        f"👥 Уровень 3: *{stats['level3_referrals']}*\n\n"
        f"*Доходы:*\n"
        f"💵 Всего заработано: *{format_usdt(stats['total_earned'])} USDT*\n"
        f"⏳ Ожидает выплаты: *{format_usdt(stats['pending_earnings'])} USDT*\n"
        f"✅ Выплачено: *{format_usdt(stats['paid_earnings'])} USDT*\n\n"
    )
    
    # Add leaderboard position if available
    referral_rank = user_position.get("referral_rank")
    earnings_rank = user_position.get("earnings_rank")
    total_users = user_position.get("total_users", 0)
    
    if referral_rank or earnings_rank:
        text += f"*Ваша позиция в рейтинге:*\n"
        if referral_rank:
            text += f"📊 По рефералам: *{referral_rank}* из {total_users}\n"
        if earnings_rank:
            text += f"💰 По заработку: *{earnings_rank}* из {total_users}\n"
        text += "\n"
    
    text += (
        f"*Комиссии:*\n"
        f"• Уровень 1: {REFERRAL_RATES[1] * 100}% от депозитов прямых партнеров\n"
        f"• Уровень 2: {REFERRAL_RATES[2] * 100}% от партнеров второго уровня\n"
        f"• Уровень 3: {REFERRAL_RATES[3] * 100}% от партнеров третьего уровня\n\n"
        f"💡 Приглашайте больше друзей и увеличивайте доход!"
    )
    
    await message.answer(text, parse_mode="Markdown", reply_markup=referral_keyboard())
