"""
Admin Users Handler
Handles user management (search, list, profile, block/unblock, balance)
"""

from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.services.admin_log_service import AdminLogService
from app.services.blacklist_service import BlacklistService, BlacklistActionType
from app.services.user_service import UserService
from bot.keyboards.reply import (
    admin_users_keyboard,
    cancel_keyboard,
    admin_user_list_keyboard,
    admin_user_profile_keyboard,
)
from bot.states.admin_states import AdminStates
from bot.utils.admin_utils import clear_state_preserve_admin_token
from bot.utils.menu_buttons import is_menu_button

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
        "Отправьте **Username** (с @ или без), **Telegram ID** или **User ID**.\n\n"
        "Пример: `@username`, `123456789`",
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

    # Try by ID first
    if identifier.isdigit():
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
    # Get users paginated (10 per page)
    limit = 10
    offset = (page - 1) * limit
    
    # Fetch users sorted by created_at desc
    stmt = select(User).order_by(desc(User.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    users = result.scalars().all()
    
    total_users = await user_service.get_total_users()
    total_pages = (total_users + limit - 1) // limit

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
    user: Any, # User model
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Show user profile and actions"""
    await clear_state_preserve_admin_token(state)
    # Save user ID in state for context actions
    await state.update_data(selected_user_id=user.id)
    
    user_service = UserService(session)
    balance_data = await user_service.get_user_balance(user.id)
    
    # Basic info
    status_emoji = "🚫" if user.is_banned else "✅"
    status_text = "Заблокирован" if user.is_banned else "Активен"
    
    text = (
        f"👤 **Профиль пользователя**\n\n"
        f"🆔 ID: `{user.id}`\n"
        f"📱 Telegram ID: `{user.telegram_id}`\n"
        f"👤 Username: @{user.username or 'Не указан'}\n"
        f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"📊 Статус: {status_emoji} **{status_text}**\n\n"
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
    # Permission check: Only extended_admin or super_admin
    from app.services.admin_service import AdminService
    
    # We can check admin role from data['admin'] object if available
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
        # Restore profile view
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

    # Update balance
    new_balance = user.balance + amount
    if new_balance < 0:
        await message.reply(
            f"❌ Нельзя списать больше, чем есть на балансе.\n"
            f"Текущий баланс: {user.balance}"
        )
        return

    # Update user
    await user_service.update_profile(user_id, balance=new_balance)
    
    # Log transaction
    admin = data.get("admin")
    admin_id = admin.id if admin else None
    
    # Security log
    from app.utils.security_logging import log_security_event
    log_security_event(
        "Admin changed user balance",
        {
            "admin_id": admin_id,
            "user_id": user_id,
            "amount": float(amount),
            "new_balance": float(new_balance)
        }
    )
    
    # Notify admin log
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
    
    # Return to profile
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
    
    # Use blacklist service for blocking
    blacklist_service = BlacklistService(session)
    admin = data.get("admin")
    admin_id = admin.id if admin else None

    if is_blocking:
        # Block
        await blacklist_service.add_to_blacklist(
            telegram_id=user.telegram_id,
            reason="Блокировка администратором через профиль",
            added_by_admin_id=admin_id,
            action_type=BlacklistActionType.BLOCKED,
        )
        user.is_banned = True
        await message.answer("✅ Пользователь заблокирован.")
    else:
        # Unblock
        # Need to deactivate blacklist entry
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
    # Check permissions - maybe super admin only? Or extended.
    admin = data.get("admin")
    if not admin or admin.role not in ["extended_admin", "super_admin"]:
        await message.answer("⛔ У вас недостаточно прав для этой операции.")
        return

    state_data = await state.get_data()
    user_id = state_data.get("selected_user_id")
    if not user_id:
        return

    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    if not user:
        return

    # Proceed with termination
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

    from app.repositories.transaction_repository import TransactionRepository
    from sqlalchemy import desc
    
    repo = TransactionRepository(session)
    # Get last 10 transactions
    txs = await repo.find_all(
        limit=10,
        user_id=user_id,
        # order_by not supported in base find_all directly this way usually, need check
    )
    # Actually find_all takes **filters. Sorting needs custom query usually.
    # Let's do query
    from app.models.transaction import Transaction
    from sqlalchemy import select
    
    stmt = select(Transaction).where(Transaction.user_id == user_id).order_by(desc(Transaction.created_at)).limit(10)
    result = await session.execute(stmt)
    txs = result.scalars().all()
    
    if not txs:
        await message.answer("📜 История транзакций пуста.")
        return
        
    text = "📜 **Последние 10 транзакций:**\n\n"
    for tx in txs:
        status = "✅" if tx.status == "confirmed" else "⏳" if tx.status == "pending" else "❌"
        text += f"{status} `{tx.created_at.strftime('%d.%m %H:%M')}`: {tx.type} **{tx.amount} USDT**\n"
        
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

    from app.services.referral_service import ReferralService
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


# Re-export or keep legacy handlers if needed for direct keyboard buttons
# But we updated the logic to use profile mainly.
# The main menu buttons "🚫 Заблокировать пользователя" still work?
# Yes, I should probably keep handle_start_block_user etc. if I want to support the old flow or redirect.
# For cleanliness, I'll remove them and guide admins to use "Find" or "List".
# But wait, `admin_users_keyboard` still has them.
# I should update `admin_users_keyboard` to REMOVE "Block" and "Terminate" direct buttons if I want to force the new flow.
# It's better UX to find user -> verify it's them -> block. Typing ID blindly to block is error prone.
# So I'll remove them from `admin_users_keyboard` in `reply.py` as well!

# Wait, let's first update `reply.py` to simplify `admin_users_keyboard`.
