     1|"""
     2|Referral Handler - ТОЛЬКО REPLY KEYBOARDS!
     3|
     4|Handles referral program actions including stats, leaderboard, and earnings.
     5|"""
     6|
     7|from typing import Any
     8|import re
     9|
    10|from aiogram import F, Router
    11|from aiogram.fsm.context import FSMContext
    12|from aiogram.types import Message
    13|from sqlalchemy.ext.asyncio import AsyncSession
    14|
    15|from app.models.user import User
    16|from app.services.referral_service import ReferralService
    17|from app.services.user_service import UserService
    18|from bot.keyboards.reply import referral_keyboard, referral_list_keyboard
    19|from bot.utils.constants import REFERRAL_RATES
    20|from bot.utils.formatters import format_usdt
    21|
    22|router = Router(name="referral")
    23|
    24|
    25|async def _show_referral_list(
    26|    message: Message,
    27|    session: AsyncSession,
    28|    user: User,
    29|    state: FSMContext,
    30|    level: int = 1,
    31|    page: int = 1,
    32|) -> None:
    33|    """
    34|    Show referral list for specific level and page.
    35|    
    36|    R4-3: Shows detailed list with dates and earnings.
    37|    R4-4: Supports pagination.
    38|    
    39|    Args:
    40|        message: Telegram message
    41|        session: Database session
    42|        user: Current user
    43|        state: FSM context
    44|        level: Referral level (1-3)
    45|        page: Page number
    46|    """
    47|    referral_service = ReferralService(session)
    48|    
    49|    # Get referrals for the level
    50|    result = await referral_service.get_referrals_by_level(
    51|        user.id, level=level, page=page, limit=10
    52|    )
    53|    
    54|    referrals = result["referrals"]
    55|    total = result["total"]
    56|    total_pages = result["pages"]
    57|    
    58|    # Save to FSM for navigation
    59|    await state.update_data(
    60|        referral_level=level,
    61|        referral_page=page,
    62|    )
    63|    
    64|    # Build message text
    65|    text = f"👥 *Мои рефералы - Уровень {level}*\n\n"
    66|    
    67|    if not referrals:
    68|        text += f"На уровне {level} у вас пока нет рефералов."
    69|    else:
    70|        text += f"*Всего рефералов уровня {level}: {total}*\n\n"
    71|        
    72|        for idx, ref in enumerate(referrals, start=1):
    73|            ref_user = ref["user"]
    74|            earned = ref["earned"]
    75|            joined_at = ref["joined_at"]
    76|            
    77|            username = ref_user.username or "без username"
    78|            # Escape Markdown chars in username
    79|            username = username.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")
    80|            date_str = joined_at.strftime("%d.%m.%Y")
    81|            
    82|            text += (
    83|                f"*{idx + (page - 1) * 10}.* @{username}\n"
    84|                f"📅 Дата регистрации: {date_str}\n"
    85|                f"💰 Заработано: *{format_usdt(earned)} USDT*\n\n"
    86|            )
    87|        
    88|        if total_pages > 1:
    89|            text += f"*Страница {page} из {total_pages}*\n\n"
    90|    
    91|    await message.answer(
    92|        text,
    93|        parse_mode="Markdown",
    94|        reply_markup=referral_list_keyboard(
    95|            level=level,
    96|            page=page,
    97|            total_pages=total_pages,
    98|        ),
    99|    )
   100|
   101|
   102|@router.message(F.text == "👥 Мои рефералы")
   103|async def handle_my_referrals(
   104|    message: Message,
   105|    session: AsyncSession,
   106|    state: FSMContext,
   107|    user: User,
   108|) -> None:
   109|    """
   110|    Show user's referrals list.
   111|    
   112|    R4-2: Checks if user has any referrals, shows message if none.
   113|    R4-3: Shows detailed list by levels.
   114|    """
   115|    referral_service = ReferralService(session)
   116|
   117|    # R4-2: Check if user has any referrals across all levels
   118|    total_referrals = 0
   119|    for level in [1, 2, 3]:
   120|        result = await referral_service.get_referrals_by_level(
   121|            user.id, level=level, page=1, limit=1
   122|        )
   123|        total_referrals += result["total"]
   124|    
   125|    # R4-2: If no referrals at all, show message
   126|    if total_referrals == 0:
   127|        text = (
   128|            "👥 *Мои рефералы*\n\n"
   129|            "У вас пока нет рефералов.\n\n"
   130|            "Приглашайте друзей по вашей реферальной ссылке "
   131|            "и получайте комиссию с их депозитов!\n\n"
   132|            "Вашу реферальную ссылку можно найти в разделе "
   133|            "\"📊 Статистика рефералов\"."
   134|        )
   135|        await message.answer(
   136|            text, parse_mode="Markdown", reply_markup=referral_keyboard()
   137|        )
   138|        return
   139|
   140|    # R4-3: Show detailed list for Level 1 by default
   141|    await _show_referral_list(message, session, user, state, level=1, page=1)
   142|
   143|
   144|@router.message(F.text.regexp(r"^📊 Уровень (\d+)$"))
   145|async def handle_referral_level_selection(
   146|    message: Message,
   147|    session: AsyncSession,
   148|    state: FSMContext,
   149|    user: User,
   150|) -> None:
   151|    """Handle referral level selection button."""
   152|    match = re.match(r"^📊 Уровень (\d+)$", message.text)
   153|    if not match:
   154|        return
   155|    
   156|    level = int(match.group(1))
   157|    if level not in [1, 2, 3]:
   158|        await message.answer("❌ Неверный уровень рефералов.")
   159|        return
   160|
   161|    await _show_referral_list(message, session, user, state, level=level, page=1)
   162|
   163|
   164|@router.message(F.text.in_(["⬅ Предыдущая страница", "➡ Следующая страница"]))
   165|async def handle_referral_pagination(
   166|    message: Message,
   167|    session: AsyncSession,
   168|    state: FSMContext,
   169|    user: User,
   170|) -> None:
   171|    """Handle referral list pagination."""
   172|    data = await state.get_data()
   173|    level = data.get("referral_level", 1)
   174|    current_page = data.get("referral_page", 1)
   175|    
   176|    if message.text == "⬅ Предыдущая страница":
   177|        page = max(1, current_page - 1)
   178|    else:
   179|        page = current_page + 1
   180|    
   181|    await _show_referral_list(message, session, user, state, level=level, page=page)
   182|
   183|
   184|@router.message(F.text == "💰 Мой заработок")
   185|async def handle_my_earnings(
   186|    message: Message,
   187|    session: AsyncSession,
   188|    user: User,
   189|) -> None:
   190|    """Show user's referral earnings."""
   191|    referral_service = ReferralService(session)
   192|
   193|    # Get referral stats
   194|    stats = await referral_service.get_referral_stats(user.id)
   195|
   196|    # R4-6: Check for zero earnings
   197|    total_earned = stats.get('total_earned', 0)
   198|    if total_earned == 0:
   199|        text = (
   200|            "💰 *Мой заработок*\n\n"
   201|            "У вас пока нет реферальных начислений.\n\n"
   202|            "💡 Приглашайте друзей по вашей реферальной ссылке, чтобы начать зарабатывать!"
   203|        )
   204|        await message.answer(
   205|            text, parse_mode="Markdown", reply_markup=referral_keyboard()
   206|        )
   207|        return
   208|
   209|    # Get pending earnings
   210|    result = await referral_service.get_pending_earnings(
   211|        user.id, page=1, limit=10
   212|    )
   213|    earnings = result["earnings"]
   214|    total_amount = result["total_amount"]
   215|
   216|    text = (
   217|        f"💰 *Мой заработок*\n\n"
   218|        f"*Доходы:*\n"
   219|        f"💵 Всего заработано: *{format_usdt(stats['total_earned'])} USDT*\n"
   220|        f"⏳ Ожидает выплаты: "
   221|        f"*{format_usdt(stats['pending_earnings'])} USDT*\n"
   222|        f"✅ Выплачено: *{format_usdt(stats['paid_earnings'])} USDT*\n\n"
   223|    )
   224|
   225|    if earnings:
   226|        text += "*Последние выплаты:*\n"
   227|        for earning in earnings[:5]:
   228|            date = earning["created_at"].strftime("%d.%m.%Y")
   229|            emoji = "✅" if earning["paid"] else "⏳"
   230|            status = 'Выплачено' if earning['paid'] else 'Ожидает'
   231|            text += (
   232|                f"{emoji} {format_usdt(earning['amount'])} USDT\n"
   233|                f"   Дата: {date}\n"
   234|                f"   Статус: {status}\n\n"
   235|            )
   236|
   237|        if total_amount > 0:
   238|            text += f"💰 Всего ожидает: *{format_usdt(total_amount)} USDT*\n"
   239|    else:
   240|        text += "У вас пока нет ожидающих выплат."
   241|
   242|    await message.answer(
   243|        text, parse_mode="Markdown", reply_markup=referral_keyboard()
   244|    )
   245|
   246|
   247|@router.message(F.text == "📊 Статистика рефералов")
   248|async def handle_referral_stats(
   249|    message: Message,
   250|    session: AsyncSession,
   251|    user: User,
   252|    **data: Any,
   253|) -> None:
   254|    """Show comprehensive referral statistics."""
   255|    referral_service = ReferralService(session)
   256|    user_service = UserService(session)
   257|
   258|    # Get referral stats
   259|    stats = await referral_service.get_referral_stats(user.id)
   260|
   261|    # Get bot info for referral link
   262|    from app.config.settings import settings
   263|    from aiogram import Bot
   264|
   265|    bot_username = settings.telegram_bot_username
   266|    # Fallback: get from bot if not in settings
   267|    if not bot_username:
   268|        bot: Bot = data.get("bot")
   269|        if bot:
   270|            bot_info = await bot.get_me()
   271|            bot_username = bot_info.username
   272|    
   273|    # Generate referral link (method now handles referral_code internally)
   274|    referral_link = user_service.generate_referral_link(user, bot_username)
   275|
   276|    # Get user position in leaderboard
   277|    user_position = await referral_service.get_user_leaderboard_position(
   278|        user.id
   279|    )
   280|
   281|    text = (
   282|        f"📊 *Статистика рефералов*\n\n"
   283|        f"*Ваша реферальная ссылка:*\n"
   284|        f"`{referral_link}`\n\n"
   285|        f"*Статистика:*\n"
   286|        f"👥 Прямые партнеры: *{stats['direct_referrals']}*\n"
   287|        f"👥 Уровень 2: *{stats['level2_referrals']}*\n"
   288|        f"👥 Уровень 3: *{stats['level3_referrals']}*\n\n"
   289|        f"*Доходы:*\n"
   290|        f"💵 Всего заработано: *{format_usdt(stats['total_earned'])} USDT*\n"
   291|        f"⏳ Ожидает выплаты: "
   292|        f"*{format_usdt(stats['pending_earnings'])} USDT*\n"
   293|        f"✅ Выплачено: *{format_usdt(stats['paid_earnings'])} USDT*\n\n"
   294|    )
   295|
   296|    # Add leaderboard position if available
   297|    referral_rank = user_position.get("referral_rank")
   298|    earnings_rank = user_position.get("earnings_rank")
   299|    total_users = user_position.get("total_users", 0)
   300|
   301|    if referral_rank or earnings_rank:
   302|        text += "*Ваша позиция в рейтинге:*\n"
   303|        if referral_rank:
   304|            text += f"📊 По рефералам: *{referral_rank}* из {total_users}\n"
   305|        if earnings_rank:
   306|            text += f"💰 По заработку: *{earnings_rank}* из {total_users}\n"
   307|        text += "\n"
   308|
   309|    text += (
   310|        f"*Комиссии:*\n"
   311|        f"• Уровень 1: {REFERRAL_RATES[1] * 100}% от депозитов прямых"
   312|            "партнеров\n"
   313|        f"• Уровень 2: {REFERRAL_RATES[2] * 100}% от партнеров второго"
   314|            "уровня\n"
   315|        f"• Уровень 3: {REFERRAL_RATES[3] * 100}% от партнеров третьего"
   316|            "уровня\n\n"
   317|        f"💡 Приглашайте больше друзей и увеличивайте доход!"
   318|    )
   319|
   320|    await message.answer(
   321|        text, parse_mode="Markdown", reply_markup=referral_keyboard()
   322|    )
   323|