"""
Referral Handler
Handles referral program actions including stats, leaderboard, and
earnings
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.referral_service import ReferralService
from app.services.user_service import UserService
from bot.keyboards.referral_keyboards import (
    get_referral_menu_keyboard,
    get_referral_stats_keyboard,
    get_referral_earnings_keyboard,
    get_back_button,
)
from bot.utils.constants import REFERRAL_RATES
from bot.utils.formatters import format_usdt


router = Router(name="referral")


@router.callback_query(F.data == "referrals")
async def handle_referrals(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
) -> None:
    """Handle referrals menu"""
    referral_service = ReferralService(session)
    user_service = UserService(session)

    # Get referral stats
    stats = await referral_service.get_referral_stats(user_id)

    message = f"""
🤝 **Реферальная программа**

**Ваша статистика:**
👥 Прямые партнеры (Уровень 1): {stats['direct_referrals']}
👥 Уровень 2: {stats['level2_referrals']}
👥 Уровень 3: {stats['level3_referrals']}

💰 **Доходы:**
💵 Всего заработано: {format_usdt(stats['total_earned'])} USDT
⏳ Ожидает выплаты: {format_usdt(stats['pending_earnings'])} USDT
✅ Выплачено: {format_usdt(stats['paid_earnings'])} USDT

**Комиссии:**
• Уровень 1: {REFERRAL_RATES[1] * 100}% от депозитов прямых партнеров
• Уровень 2: {REFERRAL_RATES[2] * 100}% от партнеров второго уровня
• Уровень 3: {REFERRAL_RATES[3] * 100}% от партнеров третьего уровня

📈 Чем больше ваша сеть, тем больше доход!
    """.strip()

    await callback.message.edit_text(
        message,
        parse_mode="Markdown",
        reply_markup=get_referral_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "referral_link")
async def handle_referral_link(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
) -> None:
    """Handle referral link"""
    user_service = UserService(session)

    # Get user
    user = await user_service.get_by_id(user_id)
    if not user:
        await callback.answer("Пользователь не найден")
        return

    # Check if user is banned
    if user.is_banned:
        await callback.answer("Реферальная ссылка деактивирована",
                              show_alert=True)
        await callback.message.edit_text(
            "🚫 **Реферальная ссылка деактивирована**\n\n"
            "Ваша реферальная ссылка была деактивирована "
            "администратором.",
            parse_mode="Markdown",
            reply_markup=get_back_button("referrals"),
        )
        return

    # Get bot info
    bot = callback.bot
    bot_info = await bot.get_me()
    referral_link = user_service.generate_referral_link(
        user.id, bot_info.username
    )

    message = f"""
🔗 **Ваша реферальная ссылка**

`{referral_link}`

**Как использовать:**
1. Скопируйте ссылку
2. Поделитесь с друзьями
3. Получайте вознаграждения от их депозитов!

**Ваши комиссии:**
• {REFERRAL_RATES[1] * 100}% от депозитов прямых партнеров
• {REFERRAL_RATES[2] * 100}% от партнеров 2-го уровня
• {REFERRAL_RATES[3] * 100}% от партнеров 3-го уровня

💡 Отправьте эту ссылку в соцсети, мессенджеры или на форумы!
    """.strip()

    await callback.message.edit_text(
        message,
        parse_mode="Markdown",
        reply_markup=get_back_button("referrals"),
    )
    await callback.answer("Ссылка готова к отправке!")


@router.callback_query(F.data.startswith("referral_stats_"))
async def handle_referral_stats(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
) -> None:
    """Handle referral stats by level"""
    referral_service = ReferralService(session)

    # Extract level from callback data
    level = int(callback.data.split("_")[-1])

    if level < 1 or level > 3:
        await callback.answer("Неверный уровень")
        return

    # Get referrals for this level
    result = await referral_service.get_referrals_by_level(
        user_id, level, page=1, limit=5
    )
    referrals = result["referrals"]
    total = result["total"]

    message = f"""
📊 **Рефералы: Уровень {level}**

**Комиссия:** {REFERRAL_RATES[level] * 100}%

"""

    if not referrals:
        message += f"У вас пока нет партнеров на уровне {level}."
    else:
        for idx, ref in enumerate(referrals, 1):
            join_date = ref["joined_at"].strftime("%d.%m.%Y")
            message += f"{idx}. {ref['display_name']}\n"
            message += f"   💰 Заработано: {format_usdt(ref['earned'])} USDT\n"
            message += f"   📅 Присоединился: {join_date}\n\n"

        message += f"\n👥 Всего партнеров: {total}"

        if total > 5:
            message += "\n📄 Показаны первые 5"

    await callback.message.edit_text(
        message,
        parse_mode="Markdown",
        reply_markup=get_referral_stats_keyboard(level),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("referral_earnings"))
async def handle_referral_earnings(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
) -> None:
    """Handle referral earnings"""
    referral_service = ReferralService(session)

    # Parse page number from callback data
    parts = callback.data.split("_")
    page = int(parts[-1]) if len(parts) > 2 else 1

    # Get pending earnings
    result = await referral_service.get_pending_earnings(
        user_id, page=page, limit=5
    )
    earnings = result["earnings"]
    total = result["total"]
    total_amount = result["total_amount"]
    pages = result["pages"]

    message = "💸 **Ожидающие выплаты**\n\n"

    if not earnings:
        message += "У вас пока нет ожидающих выплат."
    else:
        for earning in earnings:
            date = earning["created_at"].strftime("%d.%m.%Y")
            emoji = "✅" if earning["paid"] else "⏳"
            message += f"{emoji} {format_usdt(earning['amount'])} USDT\n"
            message += f"Дата: {date}\n"
            message += f"Статус: {'Выплачено' if earning['paid'] else 'Ожидает'}\n\n"

        message += f"\n💰 Всего ожидает: {format_usdt(total_amount)} USDT"
        message += f"\n📊 Всего записей: {total}"

    await callback.message.edit_text(
        message,
        parse_mode="Markdown",
        reply_markup=get_referral_earnings_keyboard(page, pages),
    )
    await callback.answer()


@router.callback_query(
    F.data.in_([
        "referral_leaderboard_referrals",
        "referral_leaderboard_earnings",
        "referral_leaderboard",
    ])
)
async def handle_referral_leaderboard(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
) -> None:
    """Handle referral leaderboard"""
    referral_service = ReferralService(session)

    # Determine view type
    view_type = "earnings" if "earnings" in callback.data else "referrals"

    # Get leaderboard data
    leaderboard = await referral_service.get_referral_leaderboard(limit=10)
    user_position = await referral_service.get_user_leaderboard_position(
        user_id
    )

    message = "🏆 **Таблица лидеров**\n\n"

    if view_type == "referrals":
        message += "**Топ по количеству рефералов:**\n\n"

        leaders = leaderboard["by_referrals"]
        if not leaders:
            message += "Пока нет рефералов в системе.\n\n"
        else:
            for leader in leaders:
                rank = leader["rank"]
                medal = (
                    "🥇"
                    if rank == 1
                    else "🥈" if rank == 2 else "🥉"
                    if rank == 3
                    else f"{rank}."
                )
                username = (
                    f"@{leader['username']}"
                    if leader["username"]
                    else f"Пользователь #{leader['telegram_id']}"
                )
                is_current = leader["user_id"] == user_id

                message += (
                    f"{medal} {username}"
                    f"{' **(вы)**' if is_current else ''}\n"
                )
                message += f"   👥 Рефералов: **{leader['referral_count']}**\n"
                message += (
                    f"   💰 Заработано: "
                    f"{format_usdt(leader['total_earnings'])} USDT\n\n"
                )

        # Show user's position if not in top 10
        referral_rank = user_position.get("referral_rank")
        total_users = user_position.get("total_users", 0)

        if referral_rank and referral_rank > 10:
            message += "---\n\n"
            message += "**Ваша позиция:**\n"
            message += f"📊 Место: {referral_rank} из {total_users}\n\n"
        elif not referral_rank and total_users > 0:
            message += "---\n\n"
            message += "**Ваша позиция:**\n"
            message += (
                "У вас пока нет рефералов. "
                "Начните приглашать друзей! 🚀\n\n"
            )
    else:
        message += "**Топ по заработку:**\n\n"

        leaders = leaderboard["by_earnings"]
        if not leaders:
            message += "Пока нет доходов в системе.\n\n"
        else:
            for leader in leaders:
                rank = leader["rank"]
                medal = (
                    "🥇"
                    if rank == 1
                    else "🥈" if rank == 2 else "🥉"
                    if rank == 3
                    else f"{rank}."
                )
                username = (
                    f"@{leader['username']}"
                    if leader["username"]
                    else f"Пользователь #{leader['telegram_id']}"
                )
                is_current = leader["user_id"] == user_id

                message += (
                    f"{medal} {username}"
                    f"{' **(вы)**' if is_current else ''}\n"
                )
                message += (
                    f"   💰 Заработано: "
                    f"**{format_usdt(leader['total_earnings'])} USDT**\n"
                )
                message += f"   👥 Рефералов: {leader['referral_count']}\n\n"

        # Show user's position if not in top 10
        earnings_rank = user_position.get("earnings_rank")
        total_users = user_position.get("total_users", 0)

        if earnings_rank and earnings_rank > 10:
            message += "---\n\n"
            message += "**Ваша позиция:**\n"
            message += f"📊 Место: {earnings_rank} из {total_users}\n\n"
        elif not earnings_rank and total_users > 0:
            message += "---\n\n"
            message += "**Ваша позиция:**\n"
            message += (
                "У вас пока нет реферального дохода. "
                "Продолжайте приглашать! 🚀\n\n"
            )

    message += "💡 Приглашайте больше друзей и поднимайтесь в рейтинге!"

    # Create keyboard with view switcher
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = [
        [
            InlineKeyboardButton(
                text=(
                    "✅ По рефералам"
                    if view_type == "referrals"
                    else "По рефералам"
                ),
                callback_data="referral_leaderboard_referrals",
            ),
            InlineKeyboardButton(
                text=(
                    "✅ По заработку"
                    if view_type == "earnings"
                    else "По заработку"
                ),
                callback_data="referral_leaderboard_earnings",
            ),
        ],
        [
            InlineKeyboardButton(
                text="◀️ Назад", callback_data="referrals"
            ),
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        message, parse_mode="Markdown", reply_markup=keyboard
    )
    await callback.answer()
