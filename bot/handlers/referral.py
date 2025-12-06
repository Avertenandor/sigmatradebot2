"""
Referral Handler - Партнёрская программа.

Handles referral program actions including stats, sharing, and earnings.
"""

from typing import Any
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.referral_service import ReferralService
from app.services.user_service import UserService
from bot.keyboards.reply import referral_keyboard, referral_list_keyboard
from bot.utils.formatters import format_usdt, escape_md

router = Router(name="referral")


# ═══════════════════════════════════════════════════════════════════════════
# SHARE REFERRAL LINK
# ═══════════════════════════════════════════════════════════════════════════


@router.message(F.text == "📤 Поделиться ссылкой")
async def handle_share_link(
    message: Message,
    session: AsyncSession,
    user: User,
    **data: Any,
) -> None:
    """Share referral link with inline buttons."""
    from app.config.settings import settings
    import urllib.parse

    user_service = UserService(session)
    bot_username = settings.telegram_bot_username
    referral_link = user_service.generate_referral_link(user, bot_username)

    # Create share text (plain, without markdown)
    share_text = (
        "🚀 Присоединяйся к SigmaTrade!\n\n"
        "💰 Инвестируй в USDT и получай до 8% в день!\n"
        "👥 Партнёрская программа до 3-х уровней\n\n"
        f"👉 {referral_link}"
    )

    # URL encode for sharing
    encoded_text = urllib.parse.quote(share_text)

    # Inline buttons for sharing
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📱 Отправить в Telegram",
                url=f"https://t.me/share/url?url={referral_link}"
                    f"&text={encoded_text}"
            )
        ],
    ])

    # Escape share_text for Markdown (URL contains _ and -)
    # Put the URL in code block to avoid Markdown parsing issues
    share_text_for_display = (
        "🚀 Присоединяйся к SigmaTrade!\n\n"
        "💰 Инвестируй в USDT и получай до 8% в день!\n"
        "👥 Партнёрская программа до 3-х уровней\n\n"
        f"👉 `{referral_link}`"
    )

    text = f"""
📤 *ПОДЕЛИТЬСЯ ССЫЛКОЙ*
{'━' * 26}

🔗 *Ваша реферальная ссылка:*
`{referral_link}`

👆 Нажмите на ссылку чтобы скопировать

{'─' * 26}
📱 *Готовый текст для друзей:*

{share_text_for_display}

{'─' * 26}
💡 Совет: Отправляйте ссылку в группы,
чаты и друзьям напрямую!
    """.strip()

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=referral_keyboard(),
    )

    # Send additional message with inline buttons
    await message.answer(
        "👇 *Быстрые действия:*",
        parse_mode="Markdown",
        reply_markup=inline_kb,
    )


# ═══════════════════════════════════════════════════════════════════════════
# MY PARTNERS (REFERRALS LIST)
# ═══════════════════════════════════════════════════════════════════════════


async def _show_referral_list(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
    level: int = 1,
    page: int = 1,
) -> None:
    """Show referral list for specific level and page."""
    referral_service = ReferralService(session)

    result = await referral_service.get_referrals_by_level(
        user.id, level=level, page=page, limit=10
    )

    referrals = result["referrals"]
    total = result["total"]
    total_pages = result["pages"]

    await state.update_data(
        referral_level=level,
        referral_page=page,
    )

    # Level names
    level_names = {1: "Прямые", 2: "2-я линия", 3: "3-я линия"}
    level_rates = {1: "3%", 2: "2%", 3: "5%"}

    text = f"""
👥 *МОИ ПАРТНЁРЫ — {level_names[level]}*
{'━' * 26}

📊 Уровень {level} | Комиссия: *{level_rates[level]}*
👥 Партнёров: *{total}*
"""

    if not referrals:
        text += "\n_На этом уровне пока нет партнёров._\n"
        text += "\n💡 Приглашайте друзей для роста команды!"
    else:
        text += f"\n{'─' * 26}\n"

        for idx, ref in enumerate(referrals, start=1):
            ref_user = ref["user"]
            earned = ref["earned"]
            joined_at = ref["joined_at"]

            username = ref_user.username or "без username"
            # Escape Markdown
            username = username.replace("_", "\\_")
            username = username.replace("*", "\\*")
            date_str = joined_at.strftime("%d.%m.%y")

            num = idx + (page - 1) * 10
            text += f"*{num}.* @{username}\n"
            text += f"   📅 {date_str} | 💰 {format_usdt(earned)}\n"

        if total_pages > 1:
            text += f"\n📄 Страница *{page}* из *{total_pages}*"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=referral_list_keyboard(
            level=level,
            page=page,
            total_pages=total_pages,
        ),
    )


@router.message(F.text == "👥 Мои партнёры")
async def handle_my_partners(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    user: User,
) -> None:
    """Show user's partners with tree visualization."""
    referral_service = ReferralService(session)

    # Get stats for all levels
    stats = await referral_service.get_referral_stats(user.id)
    l1 = stats.get('direct_referrals', 0)
    l2 = stats.get('level2_referrals', 0)
    l3 = stats.get('level3_referrals', 0)
    total = l1 + l2 + l3

    if total == 0:
        text = f"""
👥 *МОИ ПАРТНЁРЫ*
{'━' * 26}

_У вас пока нет партнёров._

{'─' * 26}
💡 *Как привлечь партнёров:*

1️⃣ Нажмите «📤 Поделиться ссылкой»
2️⃣ Отправьте друзьям или в группы
3️⃣ Получайте бонусы с их активности!

*Ваши комиссии:*
├ L1: *3%* от депозитов и ROI
├ L2: *2%* от депозитов и ROI
└ L3: *5%* от депозитов и ROI
        """.strip()

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=referral_keyboard(),
        )
        return

    # Build team tree visualization
    text = f"""
👥 *МОИ ПАРТНЁРЫ*
{'━' * 26}

*Структура команды:*

👤 *Вы*
├── 👥 L1 (прямые): *{l1}* чел.
│   └── 👥 L2 (их партнёры): *{l2}* чел.
│       └── 👥 L3 (3-я линия): *{l3}* чел.
└── 📊 *Всего в команде: {total}*

{'─' * 26}
*Комиссии по уровням:*
├ L1: *3%* — {l1} партнёров
├ L2: *2%* — {l2} партнёров
└ L3: *5%* — {l3} партнёров

{'─' * 26}
👇 *Выберите уровень для просмотра:*
    """.strip()

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=referral_list_keyboard(level=1, page=1, total_pages=1),
    )


# Handle old button name for compatibility
@router.message(F.text == "👥 Мои рефералы")
async def handle_my_referrals_compat(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    user: User,
) -> None:
    """Compatibility handler for old button."""
    await handle_my_partners(message, session, state, user)


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
        await message.answer("❌ Неверный уровень.")
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
    fsm_data = await state.get_data()
    level = fsm_data.get("referral_level", 1)
    current_page = fsm_data.get("referral_page", 1)

    if message.text == "⬅ Предыдущая страница":
        page = max(1, current_page - 1)
    else:
        page = current_page + 1

    await _show_referral_list(
        message, session, user, state, level=level, page=page
    )


# ═══════════════════════════════════════════════════════════════════════════
# MY EARNINGS
# ═══════════════════════════════════════════════════════════════════════════


@router.message(F.text == "💰 Мой заработок")
async def handle_my_earnings(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    """Show user's referral earnings with breakdown."""
    referral_service = ReferralService(session)
    stats = await referral_service.get_referral_stats(user.id)

    total_earned = stats.get('total_earned', 0)
    pending = stats.get('pending_earnings', 0)
    paid = stats.get('paid_earnings', 0)

    if total_earned == 0:
        text = f"""
💰 *МОЙ ЗАРАБОТОК*
{'━' * 26}

_У вас пока нет реферальных начислений._

{'─' * 26}
💡 *Как начать зарабатывать:*

1️⃣ Пригласите друга по ссылке
2️⃣ Он делает депозит — вы получаете *3%*
3️⃣ Он получает ROI — вы тоже получаете *3%*

Бонусы начисляются автоматически
на ваш баланс!
        """.strip()

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=referral_keyboard(),
        )
        return

    # Get pending earnings details
    result = await referral_service.get_pending_earnings(
        user.id, page=1, limit=5
    )
    earnings = result.get("earnings", [])

    text = f"""
💰 *МОЙ ЗАРАБОТОК*
{'━' * 26}

📊 *Общая статистика:*
├ 💵 Всего заработано: *{format_usdt(total_earned)}*
├ ⏳ Ожидает: *{format_usdt(pending)}*
└ ✅ Выплачено: *{format_usdt(paid)}*

{'─' * 26}
💡 *Как это работает:*

Бонусы начисляются *мгновенно* при:
├ 💳 Депозите партнёра → *вам %*
└ 📈 ROI партнёра → *вам тоже %*

Средства сразу идут на ваш баланс!
"""

    if earnings:
        text += f"\n{'─' * 26}\n"
        text += "*Последние начисления:*\n"
        for e in earnings[:5]:
            date = e["created_at"].strftime("%d.%m %H:%M")
            emoji = "✅" if e["paid"] else "⏳"
            text += f"{emoji} +{format_usdt(e['amount'])} | {date}\n"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=referral_keyboard(),
    )


# ═══════════════════════════════════════════════════════════════════════════
# DETAILED STATISTICS
# ═══════════════════════════════════════════════════════════════════════════


@router.message(F.text == "📊 Подробная статистика")
async def handle_detailed_stats(
    message: Message,
    session: AsyncSession,
    user: User,
    **data: Any,
) -> None:
    """Show comprehensive referral statistics."""
    from app.config.settings import settings

    referral_service = ReferralService(session)
    user_service = UserService(session)

    stats = await referral_service.get_referral_stats(user.id)
    bot_username = settings.telegram_bot_username
    referral_link = user_service.generate_referral_link(user, bot_username)

    # Get leaderboard position
    position = await referral_service.get_user_leaderboard_position(user.id)
    ref_rank = position.get("referral_rank")
    earn_rank = position.get("earnings_rank")
    total_users = position.get("total_users", 0)

    l1 = stats.get('direct_referrals', 0)
    l2 = stats.get('level2_referrals', 0)
    l3 = stats.get('level3_referrals', 0)
    total = l1 + l2 + l3

    text = f"""
📊 *ПОДРОБНАЯ СТАТИСТИКА*
{'━' * 26}

🔗 *Ваша ссылка:*
`{referral_link}`

{'─' * 26}
👥 *Команда:*
├ L1 (прямые): *{l1}*
├ L2 (2-я линия): *{l2}*
├ L3 (3-я линия): *{l3}*
└ 📊 Всего: *{total}*

{'─' * 26}
💰 *Доходы:*
├ Всего: *{format_usdt(stats['total_earned'])}*
├ Ожидает: *{format_usdt(stats['pending_earnings'])}*
└ Выплачено: *{format_usdt(stats['paid_earnings'])}*
"""

    if ref_rank or earn_rank:
        text += f"\n{'─' * 26}\n"
        text += "🏆 *Рейтинг:*\n"
        if ref_rank:
            text += f"├ По команде: #{ref_rank} из {total_users}\n"
        if earn_rank:
            text += f"└ По доходу: #{earn_rank} из {total_users}\n"

    text += f"""
{'─' * 26}
💎 *Ваши комиссии:*
├ L1: *3%* от депозитов + ROI
├ L2: *2%* от депозитов + ROI
└ L3: *5%* от депозитов + ROI

💡 _Комиссии начисляются автоматически_
    """.strip()

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=referral_keyboard(),
    )


# Handle old button for compatibility
@router.message(F.text == "📊 Статистика рефералов")
async def handle_stats_compat(
    message: Message,
    session: AsyncSession,
    user: User,
    **data: Any,
) -> None:
    """Compatibility handler for old stats button."""
    await handle_detailed_stats(message, session, user, **data)


# ═══════════════════════════════════════════════════════════════════════════
# HOW IT WORKS
# ═══════════════════════════════════════════════════════════════════════════


@router.message(F.text == "❓ Как это работает?")
async def handle_how_it_works(
    message: Message,
    **data: Any,
) -> None:
    """Show detailed explanation of referral program."""
    text = f"""
❓ *КАК РАБОТАЕТ ПАРТНЁРСКАЯ ПРОГРАММА*
{'━' * 26}

📋 *Пошагово:*

*1️⃣ Приглашение*
Отправьте свою ссылку другу.
Он переходит и регистрируется.
→ Теперь он ваш партнёр L1!

*2️⃣ Бонус с депозита*
Партнёр делает депозит 100 USDT
→ Вам сразу *+3 USDT* (3%)

*3️⃣ Бонус с ROI*
Партнёру начисляется ROI +2 USDT
→ Вам тоже *+0.06 USDT* (3%)

{'─' * 26}
*3 УРОВНЯ ГЛУБИНЫ:*

👤 Вы
├── 👥 L1 (ваш друг) → *3%*
│   └── 👥 L2 (его друг) → *2%*
│       └── 👥 L3 (друг друга) → *5%*

{'─' * 26}
*ПРИМЕР ДОХОДА:*

3 партнёра L1 с депозитом 100$:
├ От депозитов: 3 × 3$ = *9$*
├ От ROI (~8%/день): 3 × 0.24$ = *0.72$/день*
└ В месяц пассивно: *~22$*

А если у каждого ещё по 3 партнёра...
L2: 9 чел × 2% = *ещё больше!*

{'─' * 26}
💡 *Важно:*
• Бонусы начисляются *автоматически*
• Деньги сразу на вашем балансе
• Можно вывести в любой момент
• Нет лимитов на количество партнёров
    """.strip()

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=referral_keyboard(),
    )


# ═══════════════════════════════════════════════════════════════════════════
# BACK NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════


@router.message(F.text == "◀️ Назад к рефералам")
async def handle_back_to_referrals(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    user: User,
    **data: Any,
) -> None:
    """Go back to referral main menu."""
    from bot.handlers.menu import show_referral_menu
    await show_referral_menu(message, session, state, **{"user": user, **data})
