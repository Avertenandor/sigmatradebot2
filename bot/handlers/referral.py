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
    
    # Get level description
    level_descriptions = {
        1: ("👤", "Прямые партнёры", "3%"),
        2: ("👥", "Партнёры ваших партнёров", "2%"),
        3: ("👥👥", "Третье поколение", "5%"),
    }
    emoji, desc, rate = level_descriptions.get(level, ("👥", "Партнёры", "—"))

    # Build message text
    text = (
        f"{emoji} *Уровень {level} — {desc}*\n"
        f"📊 Ваша комиссия: *{rate}* от их депозитов и ROI\n\n"
    )

    if not referrals:
        text += (
            f"═══════════════════════════\n"
            f"На уровне {level} у вас пока нет рефералов.\n\n"
        )
        if level == 1:
            text += "💡 Поделитесь своей ссылкой чтобы привлечь партнёров!"
        elif level == 2:
            text += "💡 Ваши партнёры ещё никого не пригласили."
        else:
            text += "💡 Цепочка рефералов ещё не достигла 3 уровня."
    else:
        text += f"═══════════════════════════\n"
        text += f"📊 Всего на уровне {level}: *{total}* партнёров\n\n"

        for idx, ref in enumerate(referrals, start=1):
            ref_user = ref["user"]
            earned = ref["earned"]
            joined_at = ref["joined_at"]

            username = ref_user.username or "без username"
            # Escape Markdown chars in username
            username = username.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")
            date_str = joined_at.strftime("%d.%m.%Y")

            # Show earnings status
            if float(earned) > 0:
                earned_text = f"💰 Принёс вам: *{format_usdt(earned)} USDT*"
            else:
                earned_text = "⏳ Ещё не сделал депозит"

            text += (
                f"*{idx + (page - 1) * 10}.* @{username}\n"
                f"   📅 Присоединился: {date_str}\n"
                f"   {earned_text}\n\n"
            )

        if total_pages > 1:
            text += f"═══════════════════════════\n"
            text += f"📄 Страница *{page}* из *{total_pages}*"
    
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
    
    # R4-2: If no referrals at all, show message with explanation
    if total_referrals == 0:
        text = (
            "👥 *Мои рефералы*\n\n"
            "═══════════════════════════\n"
            "У вас пока нет приглашённых партнёров.\n\n"
            "═══════════════════════════\n"
            "💡 *Как начать зарабатывать?*\n\n"
            "1️⃣ Скопируйте свою реферальную ссылку\n"
            "   _(в разделе \"📊 Статистика рефералов\")_\n\n"
            "2️⃣ Поделитесь ей с друзьями\n\n"
            "3️⃣ Получайте % от их депозитов и ROI:\n"
            "   • 👤 Уровень 1: *3%* — прямые партнёры\n"
            "   • 👥 Уровень 2: *2%* — их партнёры\n"
            "   • 👥👥 Уровень 3: *5%* — 3-е поколение\n\n"
            "═══════════════════════════\n"
            "📌 *Пример дохода:*\n"
            "10 партнёров × депозит 100 USDT\n"
            "= *30 USDT* с депозитов\n"
            "+ ежедневный % от их ROI!"
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
    """Show user's referral earnings with detailed breakdown."""
    referral_service = ReferralService(session)

    # Get referral stats
    stats = await referral_service.get_referral_stats(user.id)

    # R4-6: Check for zero earnings
    total_earned = stats.get('total_earned', 0)
    if total_earned == 0:
        text = (
            "💰 *Мой реферальный заработок*\n\n"
            "У вас пока нет реферальных начислений.\n\n"
            "═══════════════════════════\n"
            "📚 *Как это работает?*\n\n"
            "Вы получаете % от *каждого депозита* и *ROI* ваших рефералов:\n\n"
            "👤 *Уровень 1* (прямые партнёры): *3%*\n"
            "👥 *Уровень 2* (партнёры ваших партнёров): *2%*\n"
            "👥👥 *Уровень 3* (3-е поколение): *5%*\n\n"
            "💡 *Пример:*\n"
            "Ваш реферал делает депозит 100 USDT\n"
            "→ Вы получаете *3 USDT* мгновенно!\n\n"
            "Его ROI 10 USDT за день\n"
            "→ Вы получаете *0.30 USDT* дополнительно!\n\n"
            "🔗 Вашу ссылку найдите в \"📊 Статистика рефералов\""
        )
        await message.answer(
            text, parse_mode="Markdown", reply_markup=referral_keyboard()
        )
        return

    # Get recent earnings with more details
    result = await referral_service.get_pending_earnings(
        user.id, page=1, limit=10
    )
    earnings = result.get("earnings", [])
    total_amount = result.get("total_amount", 0)

    # Calculate earnings by level
    level1_count = stats.get('direct_referrals', 0)
    level2_count = stats.get('level2_referrals', 0)
    level3_count = stats.get('level3_referrals', 0)

    text = (
        f"💰 *Мой реферальный заработок*\n\n"
        f"═══════════════════════════\n"
        f"📊 *Итого заработано:*\n"
        f"💵 Всего: *{format_usdt(stats['total_earned'])} USDT*\n"
        f"✅ Уже на балансе: *{format_usdt(stats['paid_earnings'])} USDT*\n"
        f"⏳ Ожидает начисления: *{format_usdt(stats['pending_earnings'])} USDT*\n\n"
        f"═══════════════════════════\n"
        f"👥 *Ваша команда:*\n\n"
        f"• Уровень 1 (3%): *{level1_count}* партнёров\n"
        f"• Уровень 2 (2%): *{level2_count}* партнёров\n"
        f"• Уровень 3 (5%): *{level3_count}* партнёров\n"
        f"• Всего: *{level1_count + level2_count + level3_count}* человек\n\n"
    )

    # Show recent earnings if available
    if earnings:
        text += "═══════════════════════════\n"
        text += "📜 *Последние начисления:*\n\n"
        for earning in earnings[:5]:
            date = earning.get("created_at")
            if date:
                date_str = date.strftime("%d.%m.%Y %H:%M")
            else:
                date_str = "—"
            emoji = "✅" if earning.get("paid") else "⏳"
            amount = earning.get("amount", 0)
            text += f"{emoji} *{format_usdt(amount)} USDT* — {date_str}\n"

        if total_amount > 0:
            text += f"\n💰 Всего ожидает: *{format_usdt(total_amount)} USDT*\n"

    text += (
        f"\n═══════════════════════════\n"
        f"💡 *Как увеличить доход?*\n"
        f"Приглашайте больше партнёров!\n"
        f"Ваша ссылка: \"📊 Статистика рефералов\""
    )

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
    """Show comprehensive referral statistics with potential earnings calculator."""
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

    # Calculate stats
    level1 = stats.get('direct_referrals', 0)
    level2 = stats.get('level2_referrals', 0)
    level3 = stats.get('level3_referrals', 0)
    total_referrals = level1 + level2 + level3

    text = (
        f"📊 *Реферальная программа*\n\n"
        f"═══════════════════════════\n"
        f"🔗 *Ваша ссылка для приглашения:*\n"
        f"`{referral_link}`\n"
        f"_(нажмите чтобы скопировать)_\n\n"
        f"═══════════════════════════\n"
        f"👥 *Ваша команда:*\n\n"
        f"• 👤 Уровень 1: *{level1}* чел. _(3% с их депозитов)_\n"
        f"• 👥 Уровень 2: *{level2}* чел. _(2% с их депозитов)_\n"
        f"• 👥👥 Уровень 3: *{level3}* чел. _(5% с их депозитов)_\n"
        f"• 📊 Всего: *{total_referrals}* партнёров\n\n"
        f"═══════════════════════════\n"
        f"💰 *Ваш заработок:*\n\n"
        f"💵 Всего заработано: *{format_usdt(stats['total_earned'])} USDT*\n"
        f"✅ На балансе: *{format_usdt(stats['paid_earnings'])} USDT*\n"
        f"⏳ В обработке: *{format_usdt(stats['pending_earnings'])} USDT*\n\n"
    )

    # Add leaderboard position if available
    referral_rank = user_position.get("referral_rank")
    earnings_rank = user_position.get("earnings_rank")
    total_users = user_position.get("total_users", 0)

    if referral_rank or earnings_rank:
        text += "═══════════════════════════\n"
        text += "🏆 *Ваша позиция в рейтинге:*\n\n"
        if referral_rank:
            text += f"👥 По партнёрам: *#{referral_rank}* из {total_users}\n"
        if earnings_rank:
            text += f"💰 По заработку: *#{earnings_rank}* из {total_users}\n"
        text += "\n"

    # Potential earnings calculator
    text += "═══════════════════════════\n"
    text += "🧮 *Калькулятор потенциального дохода:*\n\n"

    if total_referrals == 0:
        text += (
            "📌 *Если привлечёте 10 партнёров:*\n"
            "Каждый вносит депозит 100 USDT\n"
            "→ Вы получите *30 USDT* сразу\n"
            "→ + *3%* от их ежедневного ROI!\n\n"
            "📌 *А если у каждого из них 10 партнёров:*\n"
            "100 партнёров уровня 2\n"
            "→ *+200 USDT* с их депозитов!\n"
        )
    else:
        # Calculate potential based on current referrals
        # Assume average deposit 100 USDT
        avg_deposit = 100
        potential_l1 = level1 * avg_deposit * float(REFERRAL_RATES[1])
        potential_l2 = level2 * avg_deposit * float(REFERRAL_RATES[2])
        potential_l3 = level3 * avg_deposit * float(REFERRAL_RATES[3])
        total_potential = potential_l1 + potential_l2 + potential_l3

        text += (
            f"📌 *Если каждый партнёр внесёт 100 USDT:*\n"
            f"• От уровня 1: *{potential_l1:.2f} USDT*\n"
            f"• От уровня 2: *{potential_l2:.2f} USDT*\n"
            f"• От уровня 3: *{potential_l3:.2f} USDT*\n"
            f"• 💰 Итого: *{total_potential:.2f} USDT*\n\n"
            f"📌 *Плюс % от их ROI каждый день!*\n"
        )

    text += (
        f"\n═══════════════════════════\n"
        f"📚 *Как работает система:*\n\n"
        f"• *Уровень 1 (3%)* — те, кого вы пригласили напрямую\n"
        f"• *Уровень 2 (2%)* — партнёры ваших партнёров\n"
        f"• *Уровень 3 (5%)* — третье поколение (макс. бонус!)\n\n"
        f"💡 Вы получаете % от *депозитов* И от *ROI* рефералов!"
    )

    await message.answer(
        text, parse_mode="Markdown", reply_markup=referral_keyboard()
    )
