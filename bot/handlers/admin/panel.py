"""
Admin Panel Handler
Handles admin panel main menu and platform statistics
"""

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.models.user import User
from app.services.admin_service import AdminService
from app.services.deposit_service import DepositService
from app.services.referral_service import ReferralService
from app.services.user_service import UserService
from bot.keyboards.reply import (
    admin_keyboard,
    get_admin_keyboard_from_data,
    main_menu_reply_keyboard,
)
from bot.states.admin_states import AdminStates
from bot.utils.formatters import format_usdt

router = Router(name="admin_panel")


async def get_admin_and_super_status(
    session: AsyncSession,
    telegram_id: int | None,
    data: dict[str, Any],
) -> tuple[Admin | None, bool]:
    """
    Get admin object and super_admin status.
    
    Args:
        session: Database session
        telegram_id: Telegram user ID
        data: Handler data dict
        
    Returns:
        Tuple of (Admin object or None, is_super_admin bool)
    """
    admin: Admin | None = data.get("admin")
    if not admin and telegram_id:
        # If admin not in data (e.g., before master key auth), fetch from DB
        from app.services.admin_service import AdminService
        admin_service = AdminService(session)
        admin = await admin_service.get_admin_by_telegram_id(telegram_id)
    
    is_super_admin = admin.is_super_admin if admin else False
    return admin, is_super_admin


@router.message(AdminStates.awaiting_master_key_input)
async def handle_master_key_input(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Handle master key input for admin authentication.

    Args:
        message: Telegram message with master key
        session: Database session
        state: FSM context
        **data: Handler data
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    telegram_id = message.from_user.id if message.from_user else None
    if not telegram_id:
        await message.answer("❌ Не удалось определить пользователя")
        return

    master_key = message.text.strip() if message.text else ""

    if not master_key:
        await message.answer("❌ Мастер-ключ не может быть пустым")
        return

    # Authenticate admin
    redis_client = data.get("redis_client")
    admin_service = AdminService(session, redis_client=redis_client)
    session_obj, admin_obj, error = await admin_service.login(
        telegram_id=telegram_id,
        master_key=master_key,
        ip_address=None,  # Telegram doesn't provide IP
        user_agent=None,  # Telegram doesn't provide user agent
    )

    if error or not session_obj or not admin_obj:
        await message.answer(
            f"❌ {error or 'Ошибка аутентификации'}\n\n"
            "Попробуйте ввести мастер-ключ еще раз:",
            parse_mode="Markdown",
        )
        return

    # Save session token in FSM state
    await state.update_data(admin_session_token=session_obj.session_token)

    # Restore previous state if it exists
    state_data = await state.get_data()
    previous_state = state_data.get("auth_previous_state")
    redirect_message_text = state_data.get("auth_redirect_message")

    if previous_state:
        await state.set_state(previous_state)
        # Clean up
        await state.update_data(auth_previous_state=None, auth_redirect_message=None)

        logger.info(
            f"Admin {telegram_id} authenticated successfully, "
            f"restoring state {previous_state}"
        )

        await message.answer(
            "✅ **Аутентификация успешна!**\n\n"
            "Вы вернулись в предыдущее меню. Пожалуйста, повторите ваше действие.",
            parse_mode="Markdown",
        )
        return
        
    # Attempt to redirect based on button text if no state was restored
    if redirect_message_text:
        logger.info(f"Attempting to redirect admin {telegram_id} to '{redirect_message_text}'")
        # Clean up
        await state.update_data(auth_redirect_message=None)
        
        # Determine handler based on text
        # We need to simulate the button press
        message.text = redirect_message_text
        
        # Route to specific handlers manually if possible
        if redirect_message_text == "🆘 Техподдержка":
            from bot.handlers.admin.support import handle_admin_support_menu
            await handle_admin_support_menu(message, state, **data)
            return
        elif redirect_message_text == "💰 Управление депозитами":
            from bot.handlers.admin.deposit_management import show_deposit_management_menu
            await show_deposit_management_menu(message, session, **data)
            return
        elif redirect_message_text == "⚙️ Настроить уровни депозитов":
            from bot.handlers.admin.deposit_settings import show_deposit_settings
            await show_deposit_settings(message, session, **data)
            return
        elif redirect_message_text == "👥 Управление админами":
            from bot.handlers.admin.admins import show_admin_management
            await show_admin_management(message, session, **data)
            return
        elif redirect_message_text == "🚫 Управление черным списком":
            from bot.handlers.admin.blacklist import show_blacklist
            await show_blacklist(message, session, **data)
            return
        elif redirect_message_text == "🔐 Управление кошельком":
            from bot.handlers.admin.wallet_management import show_wallet_dashboard
            await show_wallet_dashboard(message, session, state, **data)
            return
        elif redirect_message_text == "💸 Заявки на вывод":
             await handle_admin_withdrawals(message, session, **data)
             return
        elif redirect_message_text == "📢 Рассылка":
             from bot.handlers.admin.broadcast import handle_broadcast_menu
             await handle_broadcast_menu(message, session, **data)
             return
        elif redirect_message_text == "👥 Управление пользователями":
             await handle_admin_users_menu(message, session, **data)
             return
        elif redirect_message_text == "📊 Статистика":
             await handle_admin_stats(message, session, **data)
             return
        elif redirect_message_text == "🔑 Восстановление пароля":
             from bot.handlers.admin.finpass_recovery import show_recovery_requests
             await show_recovery_requests(message, session, state, **data)
             return
        elif redirect_message_text and "Финансовая" in redirect_message_text:
             from bot.handlers.admin.financials import show_financial_list
             await show_financial_list(message, session, state, **data)
             return
    
    await state.set_state(None)  # Clear state

    logger.info(
        f"Admin {telegram_id} authenticated successfully, "
        f"session_id={session_obj.id}"
    )

    # Show admin panel
    text = """
👑 **Панель администратора**

Добро пожаловать в панель управления SigmaTrade Bot.

Выберите действие:
    """.strip()

    # Get admin and super_admin status
    telegram_id = message.from_user.id if message.from_user else None
    admin, is_super_admin = await get_admin_and_super_status(
        session, telegram_id, data
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_keyboard(is_super_admin=is_super_admin),
    )


@router.message(Command("admin"))
async def cmd_admin_panel(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Вход в админ-панель по команде /admin.
    Работает только для админов (is_admin=True из middleware).
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта команда доступна только администраторам")
        return

    user: User | None = data.get("user")
    from app.repositories.blacklist_repository import BlacklistRepository
    blacklist_repo = BlacklistRepository(session)
    blacklist_entry = None
    if user:
        blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)

    text = """
👑 **Панель администратора**

Добро пожаловать в панель управления SigmaTrade Bot.

Выберите действие:
    """.strip()

    # Get admin from data to check if super_admin
    admin: Admin | None = data.get("admin")
    is_super_admin = admin.is_super_admin if admin else False

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_keyboard(is_super_admin=is_super_admin),
    )


@router.message(F.text == "👑 Админ-панель")
async def handle_admin_panel_button(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Вход в админ-панель по кнопке в reply keyboard.
    Работает только для админов (is_admin=True из middleware).
    """
    telegram_id = message.from_user.id if message.from_user else None
    logger.info(f"[ADMIN] handle_admin_panel_button called for user {telegram_id}")
    is_admin = data.get("is_admin", False)
    logger.info(f"[ADMIN] is_admin from data: {is_admin}, data keys: {list(data.keys())}")
    
    if not is_admin:
        logger.warning(f"[ADMIN] User {telegram_id} tried to access admin panel but is_admin={is_admin}")
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    text = """
👑 **Панель администратора**

Добро пожаловать в панель управления SigmaTrade Bot.

Выберите действие:
    """.strip()

    user: User | None = data.get("user")
    from app.repositories.blacklist_repository import BlacklistRepository
    blacklist_repo = BlacklistRepository(session)
    blacklist_entry = None
    if user:
        blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)

    # Get admin and role flags for keyboard
    admin, _ = await get_admin_and_super_status(session, telegram_id, data)
    # AdminAuthMiddleware уже положил is_extended_admin / is_super_admin в data
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard_from_data(data),
    )
    # Get admin and role flags for keyboard
    admin, _ = await get_admin_and_super_status(session, telegram_id, data)

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard_from_data(data),
    )


from bot.utils.admin_utils import clear_state_preserve_admin_token


@router.message(F.text == "◀️ Главное меню")
async def handle_back_to_main_menu(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Return to main menu from admin panel"""
    from bot.handlers.menu import show_main_menu
    
    state: FSMContext = data.get("state")
    user: User | None = data.get("user")
    
    if state:
        await clear_state_preserve_admin_token(state)
    
    # Remove 'user' and 'state' from data to avoid duplicate arguments
    safe_data = {k: v for k, v in data.items() if k not in ('user', 'state')}
    await show_main_menu(message, session, user, state, **safe_data)


@router.message(Command("dashboard"))
async def cmd_dashboard(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """
    Quick dashboard with 24h metrics for admins.
    Usage: /dashboard
    """
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    from datetime import UTC, datetime, timedelta
    from sqlalchemy import select, func, and_
    from app.models.user import User
    from app.models.deposit import Deposit
    from app.models.transaction import Transaction
    from app.models.enums import TransactionStatus, TransactionType

    cutoff_24h = datetime.now(UTC) - timedelta(hours=24)

    # New users in 24h
    stmt = select(func.count(User.id)).where(User.created_at >= cutoff_24h)
    result = await session.execute(stmt)
    new_users_24h = result.scalar() or 0

    # New deposits in 24h
    stmt = select(func.count(Deposit.id), func.coalesce(func.sum(Deposit.amount), 0)).where(
        and_(
            Deposit.created_at >= cutoff_24h,
            Deposit.status == "ACTIVE",
        )
    )
    result = await session.execute(stmt)
    row = result.one()
    deposits_24h_count = row[0] or 0
    deposits_24h_amount = float(row[1] or 0)

    # Withdrawals in 24h
    stmt = select(func.count(Transaction.id), func.coalesce(func.sum(Transaction.amount), 0)).where(
        and_(
            Transaction.created_at >= cutoff_24h,
            Transaction.transaction_type == TransactionType.WITHDRAWAL.value,
            Transaction.status == TransactionStatus.COMPLETED.value,
        )
    )
    result = await session.execute(stmt)
    row = result.one()
    withdrawals_24h_count = row[0] or 0
    withdrawals_24h_amount = float(row[1] or 0)

    # Pending withdrawals
    stmt = select(func.count(Transaction.id)).where(
        and_(
            Transaction.transaction_type == TransactionType.WITHDRAWAL.value,
            Transaction.status == TransactionStatus.PENDING.value,
        )
    )
    result = await session.execute(stmt)
    pending_withdrawals = result.scalar() or 0

    # Fraud alerts (users with risk_score > 50)
    # Simplified - count banned users as proxy
    stmt = select(func.count(User.id)).where(User.is_banned == True)
    result = await session.execute(stmt)
    fraud_alerts = result.scalar() or 0

    text = (
        f"📊 *Дашборд (за 24ч)*\n\n"
        f"👥 Новых пользователей: *{new_users_24h}*\n"
        f"💰 Депозитов: *{deposits_24h_count}* ({deposits_24h_amount:.2f} USDT)\n"
        f"💸 Выводов: *{withdrawals_24h_count}* ({withdrawals_24h_amount:.2f} USDT)\n"
        f"⏳ Ожидают одобрения: *{pending_withdrawals}*\n"
        f"🚨 Заблокировано: *{fraud_alerts}*\n\n"
        f"_Обновлено: {datetime.now(UTC).strftime('%H:%M UTC')}_"
    )

    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "📊 Статистика")
async def handle_admin_stats(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle platform statistics"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    user_service = UserService(session)
    deposit_service = DepositService(session)
    referral_service = ReferralService(session)

    # Get statistics
    total_users = await user_service.get_total_users()
    verified_users = await user_service.get_verified_users()
    deposit_stats = await deposit_service.get_platform_stats()
    referral_stats = await referral_service.get_platform_referral_stats()

    # R4-X: Detailed deposit stats
    detailed_deposits = await deposit_service.get_detailed_stats()

    text = f"""
📊 **Статистика платформы**

**Пользователи:**
👥 Всего: {total_users}
✅ Верифицированы: {verified_users}
❌ Не верифицированы: {total_users - verified_users}

**Депозиты:**
💰 Всего депозитов: {deposit_stats["total_deposits"]}
💵 Общая сумма: {format_usdt(deposit_stats["total_amount"])} USDT
👤 Пользователей с депозитами: {deposit_stats["total_users"]}

**По уровням:**
• Уровень 1: {deposit_stats["deposits_by_level"].get(1, 0)} депозитов
• Уровень 2: {deposit_stats["deposits_by_level"].get(2, 0)} депозитов
• Уровень 3: {deposit_stats["deposits_by_level"].get(3, 0)} депозитов
• Уровень 4: {deposit_stats["deposits_by_level"].get(4, 0)} депозитов
• Уровень 5: {deposit_stats["deposits_by_level"].get(5, 0)} депозитов

**📋 Детализация активных депозитов:**
"""

    if not detailed_deposits:
        text += "Нет активных депозитов.\n"
    else:
        for d in detailed_deposits[:10]:  # Show top 10 recent
            next_accrual = d["next_accrual_at"].strftime("%d.%m %H:%M") if d["next_accrual_at"] else "Н/Д"
            
            # Escape username for Markdown
            username = str(d['username'])
            safe_username = username.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")
            
            text += (
                f"👤 @{safe_username} (ID: {d['user_id']})\n"
                f"   💵 Деп: {format_usdt(d['amount'])} | Выплачено: {format_usdt(d['roi_paid'])}\n"
                f"   ⏳ След. нач: {next_accrual}\n\n"
            )
        
        if len(detailed_deposits) > 10:
            text += f"... и еще {len(detailed_deposits) - 10} депозитов\n"

    text += f"""
**Рефералы:**
🤝 Всего связей: {referral_stats["total_referrals"]}
💰 Всего начислено: {format_usdt(referral_stats["total_earnings"])} USDT
✅ Выплачено: {format_usdt(referral_stats["paid_earnings"])} USDT
⏳ Ожидает выплаты: {format_usdt(referral_stats["pending_earnings"])} USDT

**По уровням:**
• Уровень 1: {referral_stats["by_level"].get(1, {}).get("count",
    0)} ({format_usdt(referral_stats["by_level"].get(1, {}).get("earnings",
        0))} USDT)
• Уровень 2: {referral_stats["by_level"].get(2, {}).get("count",
    0)} ({format_usdt(referral_stats["by_level"].get(2, {}).get(
        "earnings", 0))} USDT)
• Уровень 3: {referral_stats["by_level"].get(3, {}).get("count",
    0)} ({format_usdt(referral_stats["by_level"].get(3, {}).get(
        "earnings", 0))} USDT)
    """.strip()

    # Get admin and super_admin status
    telegram_id = message.from_user.id if message.from_user else None
    admin, is_super_admin = await get_admin_and_super_status(
        session, telegram_id, data
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_keyboard(is_super_admin=is_super_admin),
    )


@router.message(F.text == "🔐 Управление кошельком")
async def handle_admin_wallet_menu(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle wallet management menu from admin panel."""
    from app.config.settings import settings
    
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    # Проверка что пользователь - super admin
    admin_ids = settings.get_admin_ids()
    if not admin_ids or message.from_user.id != admin_ids[0]:
        await message.answer("❌ Доступ запрещён")
        return
    
    # Redirect to wallet dashboard
    from bot.handlers.admin.wallet_management import show_wallet_dashboard
    
    await show_wallet_dashboard(message, session, state, **data)


@router.message(F.text == "🚫 Управление черным списком")
async def handle_admin_blacklist_menu(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Redirect to blacklist management."""
    from bot.handlers.admin.blacklist import show_blacklist
    
    await show_blacklist(message, session, **data)


@router.message(F.text == "👥 Управление пользователями")
async def handle_admin_users_menu(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show admin users management menu"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    from bot.keyboards.reply import admin_users_keyboard
    
    text = """👥 **Управление пользователями**

Выберите действие:"""
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_users_keyboard(),
    )


@router.message(F.text == "💸 Заявки на вывод")
async def handle_admin_withdrawals(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle pending withdrawals list (admin only)"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    from app.services.withdrawal_service import WithdrawalService
    
    withdrawal_service = WithdrawalService(session)
    
    try:
        pending_withdrawals = await withdrawal_service.get_pending_withdrawals()
        
        if not pending_withdrawals:
            text = "💸 **Заявки на вывод**\n\nНет ожидающих заявок на вывод."
        else:
            text = f"💸 **Заявки на вывод**\n\nОжидающих заявок: {len(pending_withdrawals)}\n\n"
            for withdrawal in pending_withdrawals[:10]:
                text += (
                    f"• ID: {withdrawal.id}\n"
                    f"  Пользователь: {withdrawal.user_id}\n"
                    f"  Сумма: {format_usdt(withdrawal.amount)} USDT\n"
                    f"  Адрес: `{withdrawal.wallet_address}`\n\n"
                )
            
            if len(pending_withdrawals) > 10:
                text += f"... и еще {len(pending_withdrawals) - 10} заявок"
    except Exception as e:
        logger.error(f"Error getting pending withdrawals: {e}")
        text = "❌ Ошибка при получении списка заявок на вывод."
    
    # Get admin and super_admin status
    telegram_id = message.from_user.id if message.from_user else None
    admin, is_super_admin = await get_admin_and_super_status(
        session, telegram_id, data
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_keyboard(is_super_admin=is_super_admin),
    )


# Broadcast handler is now in broadcast.py as @router.message(F.text == "📢 Рассылка")


@router.message(F.text == "⚙️ Настроить уровни депозитов")
async def handle_admin_deposit_settings(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Redirect to deposit settings management (legacy)."""
    from bot.handlers.admin.deposit_settings import show_deposit_settings
    
    await show_deposit_settings(message, session, **data)


@router.message(F.text == "💰 Управление депозитами")
async def handle_admin_deposit_management(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Redirect to deposit management."""
    from bot.handlers.admin.deposit_management import show_deposit_management_menu
    
    await show_deposit_management_menu(message, session, **data)


@router.message(F.text == "👥 Управление админами")
async def handle_admin_management(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Redirect to admin management."""
    from bot.handlers.admin.admins import show_admin_management
    
    await show_admin_management(message, session, **data)
