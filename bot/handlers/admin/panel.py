"""
Admin Panel Handler
Handles admin panel main menu and platform statistics
"""

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.deposit_service import DepositService
from app.services.referral_service import ReferralService
from app.services.user_service import UserService
from bot.keyboards.reply import admin_keyboard, main_menu_reply_keyboard
from bot.utils.formatters import format_usdt

router = Router(name="admin_panel")




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

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_keyboard(),
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

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_keyboard(),
    )


@router.message(F.text == "◀️ Главное меню")
async def handle_back_to_main_menu(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Return to main menu from admin panel"""
    from bot.handlers.menu import show_main_menu
    from aiogram.fsm.context import FSMContext
    
    state: FSMContext = data.get("state")
    user: User | None = data.get("user")
    
    if state:
        await state.clear()
    
    # Remove 'user' from data to avoid duplicate argument
    data_without_user = {k: v for k, v in data.items() if k != 'user'}
    await show_main_menu(message, session, user, state, **data_without_user)


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

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_keyboard(),
    )


@router.message(F.text == "🔐 Управление кошельком")
async def handle_admin_wallet_menu(
    message: Message,
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
    
    # Redirect to wallet menu handler
    from bot.handlers.admin.wallet_key_setup import handle_wallet_menu
    
    await handle_wallet_menu(message, **data)


@router.message(F.text == "🆘 Техподдержка")
async def handle_admin_support(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle admin support tickets view."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    from app.services.support_service import SupportService
    
    support_service = SupportService(session)
    
    # Get open tickets
    pending_tickets = await support_service.list_open_tickets()
    
    if not pending_tickets:
        text = "🆘 **Техподдержка**\n\nНет ожидающих обращений."
    else:
        text = f"🆘 **Техподдержка**\n\nОжидающих обращений: {len(pending_tickets)}\n\n"
        for ticket in pending_tickets[:5]:
            text += f"• #{ticket.id} от пользователя {ticket.user_id}\n"
        
        if len(pending_tickets) > 5:
            text += f"\n... и еще {len(pending_tickets) - 5} обращений"
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_keyboard(),
    )


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
    
    # Redirect to users handler - convert to callback pattern or create message handler
    from bot.handlers.admin.users import handle_admin_users_menu as users_handler
    
    # Create a mock callback-like object or call the handler directly
    # Since we're using reply keyboard, we'll create a message-based handler
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
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_keyboard(),
    )


@router.message(F.text == "📢 Рассылка")
async def handle_admin_broadcast(
    message: Message,
    **data: Any,
) -> None:
    """Start broadcast message"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return
    
    from aiogram.fsm.context import FSMContext
    from bot.handlers.admin.broadcast import handle_start_broadcast
    
    state: FSMContext = data.get("state")
    
    # Create a mock callback to reuse existing handler
    # Or create a new message-based handler
    text = """📢 **Рассылка**

Введите сообщение для рассылки всем пользователям бота.

Вы можете отправить:
• Текст
• Фото с подписью
• Видео с подписью
• Документ

Для отмены используйте /cancel"""
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_keyboard(),
    )
    
    # Set state for broadcast
    if state:
        from bot.states.admin_states import AdminStates
        await state.set_state(AdminStates.awaiting_broadcast_message)