"""
Referral Handler - ТОЛЬКО REPLY KEYBOARDS!

Handles referral program actions including stats, leaderboard, and earnings.
"""

from typing import Any
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.referral_service import ReferralService
from app.services.user_service import UserService
from bot.keyboards.reply import referral_keyboard, referral_list_keyboard
from bot.utils.constants import REFERRAL_RATES
from bot.utils.formatters import format_usdt

router = Router(name="referral")


async def _show_referral_list(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
    level: int = 1,
    page: int = 1,
) -> None:
    """
    Show referral list for specific level and page.
    
    R4-3: Shows detailed list with dates and earnings.
    R4-4: Supports pagination.
    
    Args:
        message: Telegram message
        session: Database session
        user: Current user
        state: FSM context
        level: Referral level (1-3)
        page: Page number
    """
    referral_service = ReferralService(session)
    
    # Get referrals for the level
    result = await referral_service.get_referrals_by_level(
        user.id, level=level, page=page, limit=10
    )
    
    referrals = result["referrals"]
    total = result["total"]
    total_pages = result["pages"]
    
    # Save to FSM for navigation
    await state.update_data(
        referral_level=level,
        referral_page=page,
    )
    
    # Build message text
    text = f"👥 *Мои рефералы - Уровень {level}*\n\n"
    
    if not referrals:
        text += f"На уровне {level} у вас пока нет рефералов."
    else:
        text += f"*Всего рефералов уровня {level}: {total}*\n\n"
        
        for idx, ref in enumerate(referrals, start=1):
            ref_user = ref["user"]
            earned = ref["earned"]
            joined_at = ref["joined_at"]
            
            username = ref_user.username or "без username"
            # Escape Markdown chars in username
            username = username.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")
            date_str = joined_at.strftime("%d.%m.%Y")
            
            text += (
                f"*{idx + (page - 1) * 10}.* @{username}\n"
                f"📅 Дата регистрации: {date_str}\n"
                f"💰 Заработано: *{format_usdt(earned)} USDT*\n\n"
            )
        
        if total_pages > 1:
            text += f"*Страница {page} из {total_pages}*\n\n"
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=referral_list_keyboard(
            level=level,
            page=page,
            total_pages=total_pages,
        ),
    )


@router.message(F.text == "👥 Мои рефералы")
async def handle_my_referrals(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    user: User,
) -> None:
    """
    Show user's referrals list.
    
    R4-2: Checks if user has any referrals, shows message if none.
    R4-3: Shows detailed list by levels.
    """
    referral_service = ReferralService(session)

    # R4-2: Check if user has any referrals across all levels
    total_referrals = 0
    for level in [1, 2, 3]:
        result = await referral_service.get_referrals_by_level(
            user.id, level=level, page=1, limit=1
        )
        total_referrals += result["total"]
    
    # R4-2: If no referrals at all, show message
    if total_referrals == 0:
        text = (
            "👥 *Мои рефералы*\n\n"
            "У вас пока нет рефералов.\n\n"
            "Приглашайте друзей и получайте бонусы с *3-х уровней*!\n"
            "• Уровень 1: *3%*\n"
            "• Уровень 2: *2%*\n"
            "• Уровень 3: *5%*\n\n"
            "Вашу реферальную ссылку можно найти в разделе "
            "\"📊 Статистика рефералов\"."
        )
        await message.answer(
            text, parse_mode="Markdown", reply_markup=referral_keyboard()
        )
        return

    # R4-3: Show detailed list for Level 1 by default
    await _show_referral_list(message, session, user, state, level=1, page=1)


@router.message(F.text.regexp(r"^📊 Уровень (\d+)$"))
async def handle_referral_level_selection(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    user: User,
) -> None:
    """Handle referral level selection button."""
    match = re.match(r"^📊 Уровень (\d+)$", message.text)
    if not match:
        return
    
    level = int(match.group(1))
    if level not in [1, 2, 3]:
        await message.answer("❌ Неверный уровень рефералов.")
        return

    await _show_referral_list(message, session, user, state, level=level, page=1)


@router.message(F.text.in_(["⬅ Предыдущая страница", "➡ Следующая страница"]))
async def handle_referral_pagination(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    user: User,
) -> None:
    """Handle referral list pagination."""
    data = await state.get_data()
    level = data.get("referral_level", 1)
    current_page = data.get("referral_page", 1)
    
    if message.text == "⬅ Предыдущая страница":
        page = max(1, current_page - 1)
    else:
        page = current_page + 1
    
    await _show_referral_list(message, session, user, state, level=level, page=page)


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

    # R4-6: Check for zero earnings
    total_earned = stats.get('total_earned', 0)
    if total_earned == 0:
        text = (
            "💰 *Мой заработок*\n\n"
            "У вас пока нет реферальных начислений.\n\n"
            "💡 *Совет:* Начните строить свою команду! Ссылку можно найти в разделе "
            "\"📊 Статистика рефералов\"."
        )
        await message.answer(
            text, parse_mode="Markdown", reply_markup=referral_keyboard()
        )
        return

    # Get pending earnings
    result = await referral_service.get_pending_earnings(
        user.id, page=1, limit=10
    )
    earnings = result["earnings"]
    total_amount = result["total_amount"]

    text = (
        f"💰 *Мой заработок*\n\n"
        f"*Доходы:*\n"
        f"💵 Всего заработано: *{format_usdt(stats['total_earned'])} USDT*\n"
        f"⏳ Ожидает выплаты: "
        f"*{format_usdt(stats['pending_earnings'])} USDT*\n"
        f"✅ Выплачено: *{format_usdt(stats['paid_earnings'])} USDT*\n\n"
    )

    if earnings:
        text += "*Последние выплаты:*\n"
        for earning in earnings[:5]:
            date = earning["created_at"].strftime("%d.%m.%Y")
            emoji = "✅" if earning["paid"] else "⏳"
            status = 'Выплачено' if earning['paid'] else 'Ожидает'
            text += (
                f"{emoji} {format_usdt(earning['amount'])} USDT\n"
                f"   Дата: {date}\n"
                f"   Статус: {status}\n\n"
            )

        if total_amount > 0:
            text += f"💰 Всего ожидает: *{format_usdt(total_amount)} USDT*\n"
    else:
        text += "У вас пока нет ожидающих выплат."

    await message.answer(
        text, parse_mode="Markdown", reply_markup=referral_keyboard()
    )


@router.message(F.text == "📊 Статистика рефералов")
async def handle_referral_stats(
    message: Message,
    session: AsyncSession,
    user: User,
    **data: Any,
) -> None:
    """Show comprehensive referral statistics."""
    referral_service = ReferralService(session)
    user_service = UserService(session)

    # Get referral stats
    stats = await referral_service.get_referral_stats(user.id)

    # Get bot info for referral link
    from app.config.settings import settings
    from aiogram import Bot

    bot_username = settings.telegram_bot_username
    # Fallback: get from bot if not in settings
    if not bot_username:
        bot: Bot = data.get("bot")
        if bot:
            bot_info = await bot.get_me()
            bot_username = bot_info.username
    
    # Generate referral link (method now handles referral_code internally)
    referral_link = user_service.generate_referral_link(user, bot_username)

    # Get user position in leaderboard
    user_position = await referral_service.get_user_leaderboard_position(
        user.id
    )

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
        f"⏳ Ожидает выплаты: "
        f"*{format_usdt(stats['pending_earnings'])} USDT*\n"
        f"✅ Выплачено: *{format_usdt(stats['paid_earnings'])} USDT*\n\n"
    )

    # Add leaderboard position if available
    referral_rank = user_position.get("referral_rank")
    earnings_rank = user_position.get("earnings_rank")
    total_users = user_position.get("total_users", 0)

    if referral_rank or earnings_rank:
        text += "*Ваша позиция в рейтинге:*\n"
        if referral_rank:
            text += f"📊 По рефералам: *{referral_rank}* из {total_users}\n"
        if earnings_rank:
            text += f"💰 По заработку: *{earnings_rank}* из {total_users}\n"
        text += "\n"

    text += (
        f"*Комиссии:*\n"
        f"• Уровень 1: *{int(REFERRAL_RATES[1] * 100)}%* от депозитов прямых "
        "партнеров\n"
        f"• Уровень 2: *{int(REFERRAL_RATES[2] * 100)}%* от партнеров второго "
        "уровня\n"
        f"• Уровень 3: *{int(REFERRAL_RATES[3] * 100)}%* от партнеров третьего "
        "уровня\n\n"
        f"💡 Приглашайте больше друзей и увеличивайте доход!"
    )

    await message.answer(
        text, parse_mode="Markdown", reply_markup=referral_keyboard()
    )
