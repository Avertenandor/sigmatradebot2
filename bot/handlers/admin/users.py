"""
Admin Users Handler
Handles user management (search, list, profile, block/unblock, balance)
"""

from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from loguru import logger

from app.models.admin import Admin
from app.models.user import User
from app.models.transaction import Transaction
from app.services.admin_log_service import AdminLogService
from app.services.blacklist_service import BlacklistService, BlacklistActionType
from app.services.user_service import UserService
from app.services.referral_service import ReferralService
from bot.keyboards.reply import (
    admin_users_keyboard,
    cancel_keyboard,
    admin_user_list_keyboard,
    admin_user_profile_keyboard,
    main_menu_reply_keyboard,
)
from bot.states.admin_states import AdminStates
from bot.utils.admin_utils import clear_state_preserve_admin_token
from bot.utils.menu_buttons import is_menu_button
from bot.utils.formatters import escape_md

router = Router(name="admin_users")


@router.message(F.text == "👥 Управление пользователями")
async def handle_admin_users_menu(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show admin users menu"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    await clear_state_preserve_admin_token(state)
    
    await message.answer(
        "👥 **Управление пользователями**\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=admin_users_keyboard(),
    )


@router.message(Command("search"))
async def cmd_search_user(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Quick search user by command: /search @username or /search 0x... or /search 123456
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    # Parse argument
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "🔍 *Быстрый поиск пользователя*\n\n"
            "Использование:\n"
            "`/search @username` - по юзернейму\n"
            "`/search 123456789` - по Telegram ID\n"
            "`/search 0x...` - по адресу кошелька\n",
            parse_mode="Markdown",
        )
        return

    query = args[1].strip()
    user_service = UserService(session)
    user = None

    # Search by wallet address
    if query.startswith("0x") and len(query) == 42:
        user = await user_service.get_by_wallet(query)
    # Search by ID
    elif query.isdigit():
        user = await user_service.get_by_telegram_id(int(query))
        if not user:
            user = await user_service.get_by_id(int(query))
    # Search by username
    else:
        username = query.lstrip("@")
        user = await user_service.find_by_username(username)

    if not user:
        await message.answer(
            f"❌ Пользователь не найден: `{escape_md(query)}`",
            parse_mode="Markdown",
        )
        return

    logger.info(f"Admin search: found user {user.id} by query '{query}'")
    await show_user_profile(message, user, state, session)


@router.message(F.text == "🔍 Найти пользователя")
async def handle_find_user(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start find user flow"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    await state.set_state(AdminStates.finding_user)
    
    await message.answer(
        "🔍 **Поиск пользователя**\n\n"
        "Отправьте **Username** (с @ или без), **Telegram ID**, **User ID** "
        "или **адрес кошелька (0x...)**.\n\n"
        "Пример: `@username`, `123456789`, `0x1234...`\n\n"
        "💡 Или используйте команду: `/search @username`",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdminStates.finding_user)
async def process_find_user_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Process find user input"""
    if message.text == "❌ Отмена":
        await handle_admin_users_menu(message, state, **data)
        return

    if is_menu_button(message.text):
        await clear_state_preserve_admin_token(state)
        return

    identifier = message.text.strip()
    user_service = UserService(session)
    user = None

    # Try by wallet address
    if identifier.startswith("0x") and len(identifier) == 42:
        user = await user_service.get_by_wallet(identifier)
    # Try by ID
    elif identifier.isdigit():
        # Try as Telegram ID first (more common input)
        user = await user_service.get_by_telegram_id(int(identifier))
        # If not found, try as User ID
        if not user:
            user = await user_service.get_by_id(int(identifier))
    
    # Try by Username
    if not user:
        username = identifier.lstrip("@")
        user = await user_service.find_by_username(username)

    if not user:
        await message.reply(
            "❌ **Пользователь не найден**\n"
            "Проверьте введенные данные и попробуйте снова.",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard(),
        )
        return

    await show_user_profile(message, user, state, session)


@router.message(F.text == "👥 Список пользователей")
async def handle_list_users(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    page: int = 1,
    **data: Any,
) -> None:
    """Show paginated list of users"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    user_service = UserService(session)
    limit = 10
    offset = (page - 1) * limit
    
    # Fetch users sorted by created_at desc
    stmt = select(User).order_by(desc(User.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    users = result.scalars().all()
    
    total_users = await user_service.get_total_users()
    total_pages = (total_users + limit - 1) // limit if total_users > 0 else 1

    await state.update_data(current_user_list_page=page)
    
    if not users:
        await message.answer(
            "👥 Пользователи не найдены.",
            reply_markup=admin_users_keyboard(),
        )
        return

    text = f"👥 **Список пользователей** (Страница {page}/{total_pages})\n\n"
    text += "Выберите пользователя для просмотра профиля:"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_user_list_keyboard(users, page, total_pages),
    )


@router.message(F.text.regexp(r"^профиль\s+(\d+)$", flags=0))
async def handle_profile_by_id_command(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Open user profile card by explicit command: 'профиль <User ID>'.
    Удобно вызывать из других админских разделов (например, заявок на вывод).
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    match = re.match(r"^профиль\s+(\d+)$", message.text.strip(), re.IGNORECASE)
    if not match:
        await message.answer(
            "❌ Неверный формат. Используйте: `профиль <User ID>`",
        )
        return

    user_id = int(match.group(1))

    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    if not user:
        await message.answer(f"❌ Пользователь с ID `{user_id}` не найден.")
        return

    await show_user_profile(message, user, state, session)


@router.message(F.text == "⬅ Предыдущая")
@router.message(F.text == "Следующая ➡")
async def handle_user_list_pagination(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle list pagination"""
    state_data = await state.get_data()
    current_page = state_data.get("current_user_list_page", 1)
    
    if message.text == "⬅ Предыдущая":
        page = max(1, current_page - 1)
    else:
        page = current_page + 1
        
    await handle_list_users(message, session, state, page=page, **data)


@router.message(F.text.regexp(r"^🆔 (\d+):"))
async def handle_user_selection(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle user selection from list"""
    match = F.text.regexp(r"^🆔 (\d+):").resolve(message)
    if not match:
        return
        
    user_id = int(match.group(1))
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
        
    await show_user_profile(message, user, state, session)


async def show_user_profile(
    message: Message,
    user: Any,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Show user profile and actions"""
    await clear_state_preserve_admin_token(state)
    await state.update_data(selected_user_id=user.id)
    
    user_service = UserService(session)
    balance_data = await user_service.get_user_balance(user.id)
    
    status_emoji = "🚫" if user.is_banned else "✅"
    status_text = "Заблокирован" if user.is_banned else "Активен"
    
    # Get additional info
    referrer_info = "Не приглашен"
    if user.referrer_id:
        referrer = await user_service.get_by_id(user.referrer_id)
        if referrer:
            r_username = escape_md(referrer.username) if referrer.username else None
            referrer_info = f"@{r_username}" if r_username else f"ID {referrer.telegram_id}"
    
    fin_pass_status = "🔑 Установлен (Hash)" if user.financial_password else "❌ Не установлен"
    fin_pass_hash = f"`{user.financial_password[:15]}...`" if user.financial_password else ""
    
    verification_status = "✅ Да" if user.is_verified else "❌ Нет"
    
    phone = escape_md(user.phone) if user.phone else "Не указан"
    email = escape_md(user.email) if user.email else "Не указан"
    wallet = f"`{user.wallet_address}`" if user.wallet_address else "Не указан"
    
    last_active = user.last_active.strftime('%d.%m.%Y %H:%M') if user.last_active else "Неизвестно"
    
    # Flags
    flags = []
    if user.is_admin: flags.append("👑 Админ")
    if user.earnings_blocked: flags.append("⛔️ Начисления заблокированы")
    if user.withdrawal_blocked: flags.append("⛔️ Вывод заблокирован")
    if user.suspicious: flags.append("⚠️ Подозрительный")
    flags_text = ", ".join(flags) if flags else "Нет особых отметок"
    
    username_display = escape_md(user.username) if user.username else "Не указан"

    text = (
        f"👤 **Личное дело пользователя**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: `{user.id}`\n"
        f"📱 Telegram ID: `{user.telegram_id}`\n"
        f"👤 Username: @{username_display}\n"
        f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"🕒 Активность: {last_active}\n"
        f"📊 Статус: {status_emoji} **{status_text}**\n"
        f"✅ Верификация: {verification_status}\n"
        f"🏷 Язык: {user.language or 'ru'}\n"
        f"👥 Пригласил: {referrer_info}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔐 **Безопасность:**\n"
        f"• Фин. пароль: {fin_pass_status} {fin_pass_hash}\n"
        f"• Особые отметки: {flags_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📞 **Контакты:**\n"
        f"• Телефон: {phone}\n"
        f"• Email: {email}\n"
        f"• Кошелек: {wallet}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 **Финансы:**\n"
        f"• Баланс: `{balance_data['total_balance']:.2f} USDT`\n"
        f"• Депозиты: `{balance_data['total_deposits']:.2f} USDT`\n"
        f"• Выводы: `{balance_data['total_withdrawals']:.2f} USDT`\n"
        f"• Заработано: `{balance_data['total_earnings']:.2f} USDT`\n\n"
        f"Выберите действие:"
    )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_user_profile_keyboard(user.is_banned),
    )


@router.message(F.text == "💳 Изменить баланс")
async def handle_profile_balance(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Start balance change flow"""
    admin = data.get("admin")
    if not admin or admin.role not in ["extended_admin", "super_admin"]:
        await message.answer("⛔ У вас недостаточно прав для этой операции.")
        return

    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    if not user_id:
        await message.answer("❌ Пользователь не выбран")
        return

    await state.set_state(AdminStates.changing_user_balance)
    
    await message.answer(
        "💳 **Изменение баланса**\n\n"
        "Введите сумму для начисления (положительное число) "
        "или списания (отрицательное число).\n\n"
        "Пример: `100` (начислить) или `-50` (списать)",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdminStates.changing_user_balance)
async def process_balance_change(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Process balance change input"""
    if message.text == "❌ Отмена":
        state_data = await state.get_data()
        user_id = state_data.get("selected_user_id")
        if user_id:
            user_service = UserService(session)
            user = await user_service.get_by_id(user_id)
            if user:
                await show_user_profile(message, user, state, session)
                return
        await handle_admin_users_menu(message, state, **data)
        return

    try:
        amount = Decimal(message.text.replace(",", "."))
        if amount == 0:
            raise ValueError("Amount cannot be zero")
    except Exception:
        await message.reply("❌ Введите корректное число (например: 100 или -50)")
        return

    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    if not user_id:
        await message.answer("❌ Пользователь не выбран")
        await handle_admin_users_menu(message, state, **data)
        return

    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return

    new_balance = user.balance + amount
    if new_balance < 0:
        await message.reply(
            f"❌ Нельзя списать больше, чем есть на балансе.\n"
            f"Текущий баланс: {user.balance}"
        )
        return

    await user_service.update_profile(user_id, balance=new_balance)
    
    admin = data.get("admin")
    admin_id = admin.id if admin else None
    
    # Security log (simplified usage)
    from loguru import logger
    logger.warning(f"Admin {admin_id} changed balance for user {user_id} by {amount}. New: {new_balance}")
    
    admin_log = AdminLogService(session)
    action = "Начисление" if amount > 0 else "Списание"
    await admin_log.log_action(
        admin_id=admin_id,
        action=f"balance_change_{'credit' if amount > 0 else 'debit'}",
        entity_type="user",
        entity_id=user_id,
        details={"amount": float(amount), "old_balance": float(user.balance - amount), "new_balance": float(new_balance)},
        ip_address=None
    )

    await message.answer(
        f"✅ Баланс успешно изменен.\n"
        f"{action}: {amount} USDT\n"
        f"Новый баланс: {new_balance} USDT"
    )
    
    await show_user_profile(message, user, state, session)


@router.message(F.text.in_({"🚫 Заблокировать", "✅ Разблокировать"}))
async def handle_profile_block_toggle(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Toggle block status"""
    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    if not user_id:
        return

    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    if not user:
        return

    is_blocking = message.text == "🚫 Заблокировать"
    blacklist_service = BlacklistService(session)
    admin = data.get("admin")
    admin_id = admin.id if admin else None

    if is_blocking:
        await blacklist_service.add_to_blacklist(
            telegram_id=user.telegram_id,
            reason="Блокировка администратором через профиль",
            added_by_admin_id=admin_id,
            action_type=BlacklistActionType.BLOCKED,
        )
        user.is_banned = True
        await message.answer("✅ Пользователь заблокирован.")
    else:
        entry = await blacklist_service.repo.find_by_telegram_id(user.telegram_id)
        if entry and entry.is_active:
            await blacklist_service.repo.update(entry.id, is_active=False)
        
        user.is_banned = False
        await message.answer("✅ Пользователь разблокирован.")
    
    await session.commit()
    await show_user_profile(message, user, state, session)


@router.message(F.text == "⚠️ Терминировать аккаунт")
async def handle_profile_terminate(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Terminate account"""
    admin = data.get("admin")
    if not admin or admin.role not in ["extended_admin", "super_admin"]:
        await message.answer("⛔ У вас недостаточно прав для этой операции.")
        return

    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    if not user_id:
        # Fallback to legacy flow check if state is not set
        if await state.get_state() == AdminStates.awaiting_user_to_terminate:
             # This is part of the legacy flow which we are restoring below
             pass
        else:
             return

    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    if not user:
        return

    blacklist_service = BlacklistService(session)
    admin_id = admin.id if admin else None

    await blacklist_service.add_to_blacklist(
        telegram_id=user.telegram_id,
        reason="Терминация администратором через профиль",
        added_by_admin_id=admin_id,
        action_type=BlacklistActionType.TERMINATED,
    )
    user.is_banned = True
    await session.commit()
    
    await message.answer("✅ Аккаунт терминирован.")
    await show_user_profile(message, user, state, session)


@router.message(F.text == "📜 История транзакций")
async def handle_profile_history(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Show transaction history"""
    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    if not user_id:
        return

    stmt = select(Transaction).where(Transaction.user_id == user_id).order_by(desc(Transaction.created_at)).limit(10)
    result = await session.execute(stmt)
    txs = result.scalars().all()
    
    if not txs:
        await message.answer("📜 История транзакций пуста.")
        return
        
    text = "📜 **Последние 10 транзакций:**\n\n"
    for tx in txs:
        status_map = {
            "confirmed": "✅",
            "pending": "⏳",
            "failed": "❌",
            "rejected": "🚫"
        }
        status = status_map.get(tx.status, "❓")
        text += f"{status} `{tx.created_at.strftime('%d.%m %H:%M')}`: {tx.type} **{tx.amount} USDT**\n"
        if tx.tx_hash:
            text += f"   🔗 `{tx.tx_hash}`\n"
        
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "👥 Рефералы")
async def handle_profile_referrals(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Show referrals info"""
    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    if not user_id:
        return

    service = ReferralService(session)
    stats = await service.get_referral_stats(user_id)
    
    text = (
        "👥 **Реферальная статистика**\n\n"
        f"Level 1: **{stats['level_1_count']}** партнёров\n"
        f"Level 2: **{stats['level_2_count']}** партнёров\n"
        f"Level 3: **{stats['level_3_count']}** партнёров\n\n"
        f"💰 Всего заработано: **{stats['total_earned']:.2f} USDT**"
    )
    
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "◀️ К списку пользователей")
async def handle_back_to_list(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Return to list"""
    state_data = await state.get_data()
    page = state_data.get("current_user_list_page", 1)
    await handle_list_users(message, session, state, page=page, **data)


@router.message(F.text == "👑 Админ-панель")
async def handle_back_to_admin_panel(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Return to admin panel from users menu"""
    from bot.handlers.admin.panel import handle_admin_panel_button
    await handle_admin_panel_button(message, session, **data)


# =================================================================================================
# Legacy / Direct Button Handlers (Restored)
# =================================================================================================

@router.message(F.text == "🚫 Заблокировать пользователя")
async def handle_start_block_user(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start block user flow"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    await state.set_state(AdminStates.awaiting_user_to_block)

    text = """
🚫 **Блокировка пользователя**

Отправьте username (с @) или Telegram ID пользователя для блокировки.

Пользователь получит уведомление и сможет подать апелляцию "
        "в течение 3 рабочих дней."

Пример: `@username` или `123456789`
    """.strip()

    await message.answer(
        text, parse_mode="Markdown", reply_markup=cancel_keyboard()
    )


@router.message(AdminStates.awaiting_user_to_block)
async def handle_block_user_input(  # noqa: C901
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle block user input"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "❌ Блокировка отменена.",
            reply_markup=admin_users_keyboard(),
        )
        return

    if message.text and is_menu_button(message.text):
        await clear_state_preserve_admin_token(state)
        return

    from loguru import logger
    from app.services.blacklist_service import BlacklistService
    from app.repositories.system_setting_repository import SystemSettingRepository
    from aiogram import Bot
    from app.config.settings import settings
    from app.repositories.blacklist_repository import BlacklistRepository

    user_service = UserService(session)
    blacklist_service = BlacklistService(session)

    identifier = message.text.strip() if message.text else ""

    if not identifier:
        await message.reply("❌ Отправьте username или ID")
        return

    user = None
    if identifier.startswith("@"):
        username = identifier[1:]
        user = await user_service.find_by_username(username)
    elif identifier.isdigit():
        telegram_id = int(identifier)
        user = await user_service.get_by_telegram_id(telegram_id)
    else:
        try:
            telegram_id = int(identifier)
            user = await user_service.get_by_telegram_id(telegram_id)
        except ValueError:
            user = None

    if not user:
        await message.reply("❌ Пользователь не найден")
        await clear_state_preserve_admin_token(state)
        return

    admin = data.get("admin")
    admin_id = admin.id if admin else None

    try:
        await blacklist_service.add_to_blacklist(
            telegram_id=user.telegram_id,
            reason="Блокировка администратором",
            added_by_admin_id=admin_id,
            action_type=BlacklistActionType.BLOCKED,
        )

        user.is_banned = True
        await session.commit()

        try:
            bot = Bot(token=settings.telegram_bot_token)
            setting_repo = SystemSettingRepository(session)
            notification_text = await setting_repo.get_value(
                "blacklist_block_notification_text",
                default=(
                    "⚠️ Ваш аккаунт временно заблокирован в нашем сообществе. "
                    "Вы можете подать апелляцию в течение 3 рабочих дней."
                )
            )
            notification_text_with_instruction = (
                f"{notification_text}\n\n"
                "Чтобы подать апелляцию, нажмите кнопку "
                "'📝 Подать апелляцию' в боте."
            )
            await bot.send_message(
                chat_id=user.telegram_id,
                text=notification_text_with_instruction,
            )
            
            blacklist_repo = BlacklistRepository(session)
            blacklist_entry = await blacklist_repo.find_by_telegram_id(
                user.telegram_id
            )
            await bot.send_message(
                chat_id=user.telegram_id,
                text="Выберите действие:",
                reply_markup=main_menu_reply_keyboard(
                    user=user, blacklist_entry=blacklist_entry, is_admin=False
                ),
            )
            await bot.session.close()
        except Exception as e:
            logger.warning(f"Failed to send notification to user {user.telegram_id}: {e}")

        username = escape_md(user.username) if user.username else None
        display_name = f"@{username}" if username else f"ID {user.telegram_id}"
        
        await message.reply(
            f"✅ Пользователь {display_name} заблокирован.\n"
            f"Уведомление отправлено пользователю.",
            reply_markup=admin_users_keyboard(),
        )

        if admin:
            log_service = AdminLogService(session)
            await log_service.log_user_blocked(
                admin=admin,
                user_id=user.id,
                user_telegram_id=user.telegram_id,
                reason="Блокировка администратором",
            )
            
    except Exception as e:
        logger.error(f"Error blocking user: {e}")
        await message.reply(
            f"❌ Ошибка: {str(e)}",
            reply_markup=admin_users_keyboard(),
        )

    await clear_state_preserve_admin_token(state)


# Re-use handle_profile_terminate but support direct call with state
@router.message(AdminStates.awaiting_user_to_terminate)
async def handle_terminate_user_input(  # noqa: C901
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle terminate user input (direct flow)"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    if message.text == "❌ Отмена":
        await clear_state_preserve_admin_token(state)
        await message.answer(
            "❌ Терминация отменена.",
            reply_markup=admin_users_keyboard(),
        )
        return

    if message.text and is_menu_button(message.text):
        await clear_state_preserve_admin_token(state)
        return

    from loguru import logger
    from app.services.blacklist_service import BlacklistService
    from app.repositories.system_setting_repository import SystemSettingRepository
    from aiogram import Bot
    from app.config.settings import settings

    user_service = UserService(session)
    blacklist_service = BlacklistService(session)

    identifier = message.text.strip() if message.text else ""

    if not identifier:
        await message.reply("❌ Отправьте username или ID")
        return

    user = None
    if identifier.startswith("@"):
        username = identifier[1:]
        user = await user_service.find_by_username(username)
    elif identifier.isdigit():
        telegram_id = int(identifier)
        user = await user_service.get_by_telegram_id(telegram_id)
    else:
        try:
            telegram_id = int(identifier)
            user = await user_service.get_by_telegram_id(telegram_id)
        except ValueError:
            user = None

    if not user:
        await message.reply("❌ Пользователь не найден")
        await clear_state_preserve_admin_token(state)
        return

    admin = data.get("admin")
    admin_id = admin.id if admin else None

    try:
        await blacklist_service.add_to_blacklist(
            telegram_id=user.telegram_id,
            reason="Терминация администратором",
            added_by_admin_id=admin_id,
            action_type=BlacklistActionType.TERMINATED,
        )

        user.is_banned = True
        await session.commit()

        try:
            bot = Bot(token=settings.telegram_bot_token)
            setting_repo = SystemSettingRepository(session)
            notification_text = await setting_repo.get_value(
                "blacklist_terminate_notification_text",
                default=(
                    "❌ Ваш аккаунт терминирован в нашем сообществе "
                    "без возможности восстановления."
                )
            )
            await bot.send_message(
                chat_id=user.telegram_id,
                text=notification_text,
            )
            await bot.session.close()
        except Exception as e:
            logger.warning(f"Failed to send notification to user {user.telegram_id}: {e}")

        username = escape_md(user.username) if user.username else None
        display_name = f"@{username}" if username else f"ID {user.telegram_id}"
        
        await message.reply(
            f"✅ Аккаунт {display_name} терминирован.\n"
            f"Уведомление отправлено пользователю.",
            reply_markup=admin_users_keyboard(),
        )

        if admin:
            log_service = AdminLogService(session)
            await log_service.log_user_terminated(
                admin=admin,
                user_id=user.id,
                user_telegram_id=user.telegram_id,
                reason="Терминация администратором",
            )
    except Exception as e:
        logger.error(f"Error terminating user: {e}")
        await message.reply(
            f"❌ Ошибка: {str(e)}",
            reply_markup=admin_users_keyboard(),
        )

    await clear_state_preserve_admin_token(state)

@router.message(F.text == "⚠️ Терминировать аккаунт")
async def handle_start_terminate_user_direct(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start terminate user flow (direct)"""
    # Check permissions first (this is triggered by button)
    # Note: handle_profile_terminate also catches this text!
    # We need to differentiate based on state or context.
    # If we are in profile mode (selected_user_id set), handle_profile_terminate should take precedence.
    # But handlers are registered in order.
    # handle_profile_terminate is registered BEFORE this one.
    # So if state has selected_user_id, handle_profile_terminate will run.
    # If not, it will return early (if not user_id: return).
    # So we can put this handler AFTER handle_profile_terminate and it will catch cases where profile is not active.
    
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    await state.set_state(AdminStates.awaiting_user_to_terminate)

    text = """
⚠️ **Терминация аккаунта**

Отправьте username (с @) или Telegram ID пользователя для терминации.

⚠️ **ВНИМАНИЕ:** Аккаунт будет полностью заблокирован без возможности апелляции.

Пример: `@username` или `123456789`
    """.strip()

    await message.answer(
        text, parse_mode="Markdown", reply_markup=cancel_keyboard()
    )
