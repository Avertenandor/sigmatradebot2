"""
Withdrawal handler.

Handles withdrawal request flow.
"""

from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.exc import OperationalError, InterfaceError, DatabaseError

from app.models.user import User
from app.services.user_service import UserService
from app.services.withdrawal_service import WithdrawalService
from bot.keyboards.reply import (
    main_menu_reply_keyboard,
    withdrawal_keyboard,
    withdrawal_history_keyboard,
)
from bot.states.withdrawal import WithdrawalStates
from bot.utils.formatters import format_usdt
from bot.utils.menu_buttons import is_menu_button

router = Router()


@router.message(F.text == "💸 Вывести всю сумму")
async def withdraw_all(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Withdraw all available balance.
    
    Uses session_factory for short transaction to get balance.

    Args:
        message: Telegram message
        state: FSM state
        data: Additional data including session_factory and user
    """
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        return

    # R11-2: Check blockchain maintenance mode
    from app.config.settings import settings
    if settings.blockchain_maintenance_mode:
        await message.answer(
            "⚠️ Временная приостановка выводов из-за проблем с сетью "
            "Binance Smart Chain.\n\n"
            "Ваши средства в безопасности, выводы будут доступны после "
            "восстановления.\n\n"
            "Следите за обновлениями в нашем канале.",
            reply_markup=withdrawal_keyboard(),
        )
        return
    
    # Check verification status (from TZ: withdrawals require verification)
    if not user.is_verified:
        await message.answer(
            "❌ Вывод недоступен до верификации!\n\n"
            "Для вывода средств необходимо пройти верификацию.\n"
            "Сначала нажмите '✅ Пройти верификацию' в главном меню.",
            reply_markup=withdrawal_keyboard(),
        )
        return

    # Check withdrawal rate limit
    telegram_id = message.from_user.id if message.from_user else None
    if telegram_id:
        from bot.utils.operation_rate_limit import OperationRateLimiter

        redis_client = data.get("redis_client")
        rate_limiter = OperationRateLimiter(redis_client=redis_client)
        allowed, error_msg = await rate_limiter.check_withdrawal_limit(
            telegram_id
        )
        if not allowed:
            await message.answer(
                error_msg or "Слишком много заявок на вывод",
                reply_markup=withdrawal_keyboard(),
            )
            return

    session_factory = data.get("session_factory")
    
    # Get balance with SHORT transaction
    if not session_factory:
        # Fallback
        session = data.get("session")
        if not session:
            await message.answer("❌ Системная ошибка. Отправьте /start или обратитесь в поддержку.")
            return
        user_service = UserService(session)
        balance = await user_service.get_user_balance(user.id)
    else:
        # NEW pattern: short read transaction
        async with session_factory() as session:
            async with session.begin():
                user_service = UserService(session)
                balance = await user_service.get_user_balance(user.id)
        # Transaction closed here

    if not balance or balance["available_balance"] == 0:
        await message.answer(
            "❌ Недостаточно средств для вывода",
            reply_markup=withdrawal_keyboard(),
        )
        return

    available = Decimal(str(balance["available_balance"]))

    # Check minimum
    min_amount = WithdrawalService.get_min_withdrawal_amount()
    if available < min_amount:
        await message.answer(
            f"❌ Минимальная сумма вывода: {min_amount} USDT",
            reply_markup=withdrawal_keyboard(),
        )
        return

    # Save amount and ask for password
    await state.update_data(amount=available)

    text = (
        f"💸 *Вывод всех средств*\n\n"
        f"Сумма: *{available} USDT*\n\n"
        f"Для подтверждения введите ваш финансовый пароль:"
    )

    await message.answer(text, parse_mode="Markdown")
    await state.set_state(WithdrawalStates.waiting_for_financial_password)


@router.message(F.text == "💵 Вывести указанную сумму")
async def withdraw_amount(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Withdraw specific amount.

    Args:
        message: Telegram message
        state: FSM state
        data: Additional data including user
    """
    # R11-2: Check blockchain maintenance mode
    from app.config.settings import settings
    if settings.blockchain_maintenance_mode:
        await message.answer(
            "⚠️ Временная приостановка выводов из-за проблем с сетью "
            "Binance Smart Chain.\n\n"
            "Ваши средства в безопасности, выводы будут доступны после "
            "восстановления.\n\n"
            "Следите за обновлениями в нашем канале.",
            reply_markup=withdrawal_keyboard(),
        )
        return

    text = (
        f"💸 *Вывод средств*\n\n"
        f"Введите сумму вывода в USDT:\n\n"
        f"Минимальная сумма: "
        f"*{WithdrawalService.get_min_withdrawal_amount()} USDT*"
    )

    await message.answer(text, parse_mode="Markdown")
    await state.set_state(WithdrawalStates.waiting_for_amount)


@router.message(WithdrawalStates.waiting_for_amount)
async def process_withdrawal_amount(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Process withdrawal amount.
    
    Uses session_factory for short transaction to validate balance.

    Args:
        message: Telegram message
        state: FSM state
        data: Additional data including session_factory and user
    """
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    # Check verification status (from TZ: withdrawals require verification)
    if not user.is_verified:
        await message.answer(
            "❌ Вывод недоступен до верификации!\n\n"
            "Для вывода средств необходимо пройти верификацию.\n"
            "Сначала нажмите '✅ Пройти верификацию' в главном меню.",
            reply_markup=withdrawal_keyboard(),
        )
        await state.clear()
        return

    # Check if message is a menu button - if so, clear state and ignore
    if is_menu_button(message.text or ""):
        await state.clear()
        return  # Let menu handlers process this

    try:
        amount = Decimal((message.text or "").strip())
    except (ValueError, ArithmeticError):
        await message.answer(
            "❌ Неверный формат суммы!\n\n"
            "Введите число (например: 100 или 100.50):"
        )
        return

    # Check minimum
    min_amount = WithdrawalService.get_min_withdrawal_amount()
    if amount < min_amount:
        await message.answer(
            f"❌ Сумма слишком маленькая!\n\n"
            f"Минимальная сумма: {min_amount} USDT\n"
            f"Попробуйте еще раз:"
        )
        return

    session_factory = data.get("session_factory")
    
    # Check balance with SHORT transaction
    if not session_factory:
        # Fallback
        session = data.get("session")
        if not session:
            await message.answer("❌ Системная ошибка. Отправьте /start или обратитесь в поддержку.")
            await state.clear()
            return
        user_service = UserService(session)
        balance = await user_service.get_user_balance(user.id)
    else:
        # NEW pattern: short read transaction
        async with session_factory() as session:
            async with session.begin():
                user_service = UserService(session)
                balance = await user_service.get_user_balance(user.id)
        # Transaction closed here

    if not balance or Decimal(str(balance["available_balance"])) < amount:
        await message.answer(
            f"❌ Недостаточно средств!\n\n"
            f"Доступно: {balance['available_balance']:.2f} USDT\n"
            f"Попробуйте меньшую сумму:"
        )
        return

    # Save amount and ask for password
    await state.update_data(amount=amount)

    text = (
        f"💸 Вывод средств\n\n"
        f"Сумма: {amount} USDT\n\n"
        f"Для подтверждения введите ваш финансовый пароль:"
    )

    await message.answer(text)
    await state.set_state(WithdrawalStates.waiting_for_financial_password)


@router.message(WithdrawalStates.waiting_for_financial_password)
async def process_financial_password(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Process financial password and create withdrawal.
    
    CRITICAL: Uses session_factory for short transaction during withdrawal creation.

    Args:
        message: Telegram message
        state: FSM state
        data: Additional data including session_factory and user
    """
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    # Check if message is a menu button - if so, clear state and ignore
    if is_menu_button(message.text or ""):
        await state.clear()
        return  # Let menu handlers process this
    
    # Check withdrawal rate limit before creating withdrawal
    telegram_id = message.from_user.id if message.from_user else None
    if telegram_id:
        from bot.utils.operation_rate_limit import OperationRateLimiter

        redis_client = data.get("redis_client")
        rate_limiter = OperationRateLimiter(redis_client=redis_client)
        allowed, error_msg = await rate_limiter.check_withdrawal_limit(
            telegram_id
        )
        if not allowed:
            await message.answer(
                error_msg or "Слишком много заявок на вывод",
                reply_markup=withdrawal_keyboard(),
            )
            await state.clear()
            return
    
    password = (message.text or "").strip()

    # Delete message with password (safe delete)
    try:
        await message.delete()
    except Exception:
        pass  # Message already deleted or not available

    session_factory = data.get("session_factory")
    
    # Verify password and create withdrawal with SHORT transaction
    if not session_factory:
        # Fallback
        session = data.get("session")
        if not session:
            await message.answer("❌ Системная ошибка. Отправьте /start или обратитесь в поддержку.")
            await state.clear()
            return
        
        try:
            user_service = UserService(session)
            
            # Verify financial password (CRITICAL: must use await and user.id)
            is_valid = await user_service.verify_financial_password(user.id, password)
            if not is_valid:
                await message.answer(
                    "❌ Неверный финансовый пароль!\n\nПопробуйте еще раз:"
                )
                return
            
            # Get amount from state
            state_data = await state.get_data()
            amount = state_data.get("amount")
            
            # Get fresh user from DB to check earnings_blocked
            current_user = await user_service.get_by_id(user.id)
            if not current_user:
                await message.answer("❌ Ошибка: пользователь не найден")
                await state.clear()
                return
            
            # Unblock earnings if blocked (after successful finpass verification)
            if current_user.earnings_blocked:
                await user_service.block_earnings(user.id, block=False)
                logger.info(
                    "Earnings unblocked after successful finpass usage",
                    extra={"user_id": user.id, "telegram_id": user.telegram_id},
                )
            
            # Get balance
            balance = await user_service.get_user_balance(user.id)
            
            # Create withdrawal
            withdrawal_service = WithdrawalService(session)
            transaction, error = await withdrawal_service.request_withdrawal(
                user_id=user.id,
                amount=amount,
                available_balance=Decimal(str(balance["available_balance"])),
            )

            # R15-3: If withdrawal successful, auto-reject finpass recovery
            if transaction and not error:
                await withdrawal_service.handle_successful_withdrawal_with_old_password(
                    user.id
                )
        except (OperationalError, InterfaceError, DatabaseError) as e:
            # R3-15: Handle database errors in fallback path
            logger.error(f"Database error during withdrawal (fallback) for user {user.id}: {e}")
            await session.rollback()
            is_admin = data.get("is_admin", False)
            blacklist_entry = data.get("blacklist_entry")
            if blacklist_entry is None and user:
                from app.repositories.blacklist_repository import BlacklistRepository
                blacklist_repo = BlacklistRepository(session)
                blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
            await message.answer(
                "❌ Ошибка при создании заявки, попробуйте позже",
                reply_markup=main_menu_reply_keyboard(
                    user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
                ),
            )
            await state.clear()
            return
    else:
        # NEW pattern: short transaction for CRITICAL withdrawal creation
        try:
            async with session_factory() as session:
                async with session.begin():
                    user_service = UserService(session)
                    
                    # Verify financial password (CRITICAL: must use await and user.id)
                    is_valid = await user_service.verify_financial_password(user.id, password)
                    if not is_valid:
                        await message.answer(
                            "❌ Неверный финансовый пароль!\n\nПопробуйте еще раз:"
                        )
                        return
                    
                    # Get amount from state
                    state_data = await state.get_data()
                    amount = state_data.get("amount")
                    
                    # Get fresh user from DB to check earnings_blocked
                    current_user = await user_service.get_by_id(user.id)
                    if not current_user:
                        await message.answer("❌ Ошибка: пользователь не найден")
                        await state.clear()
                        return
                    
                    # Unblock earnings if blocked (after successful finpass verification)
                    # This happens in the same transaction as withdrawal creation
                    if current_user.earnings_blocked:
                        await user_service.block_earnings(user.id, block=False)
                        logger.info(
                            "Earnings unblocked after successful finpass usage",
                            extra={"user_id": user.id, "telegram_id": user.telegram_id},
                        )
                    
                    # Get balance
                    balance = await user_service.get_user_balance(user.id)
                    
                    # Create withdrawal
                    withdrawal_service = WithdrawalService(session)
                    transaction, error = await withdrawal_service.request_withdrawal(
                        user_id=user.id,
                        amount=amount,
                        available_balance=Decimal(str(balance["available_balance"])),
                    )
            # Transaction closed here - BEFORE notifications
        except (OperationalError, InterfaceError, DatabaseError) as e:
            # R3-15: Handle database errors
            logger.error(f"Database error during withdrawal for user {user.id}: {e}")
            is_admin = data.get("is_admin", False)
            blacklist_entry = data.get("blacklist_entry")
            if blacklist_entry is None and user:
                from app.repositories.blacklist_repository import BlacklistRepository
                # Use session_factory for blacklist check
                async with session_factory() as session:
                    blacklist_repo = BlacklistRepository(session)
                    blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
            await message.answer(
                "❌ Ошибка при создании заявки, попробуйте позже",
                reply_markup=main_menu_reply_keyboard(
                    user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
                ),
            )
            await state.clear()
            return

    if error:
        is_admin = data.get("is_admin", False)
        # Try to get from middleware first
        blacklist_entry = data.get("blacklist_entry")
        if blacklist_entry is None and user:
            from app.repositories.blacklist_repository import BlacklistRepository
            blacklist_repo = BlacklistRepository(session)
            blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
        await message.answer(
            f"❌ Ошибка создания заявки:\n{error}",
            reply_markup=main_menu_reply_keyboard(
                user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
            ),
        )
        await state.clear()
        return

    if transaction:
        logger.info(
            "Withdrawal requested",
            extra={
                "transaction_id": transaction.id,
                "user_id": user.id,
                "amount": str(amount),
            },
        )

        text = (
            f"✅ Заявка на вывод создана!\n\n"
            f"💰 Сумма: {amount} USDT\n"
            f"🆔 ID заявки: {transaction.id}\n"
            f"📍 Адрес: {user.masked_wallet}\n\n"
            f"⏳ Заявка находится на рассмотрении.\n"
            f"Обычно обработка занимает от 1 до 24 часов.\n\n"
            f"Вы получите уведомление после обработки."
        )

        is_admin = data.get("is_admin", False)
        # Try to get from middleware first
        blacklist_entry = data.get("blacklist_entry")
        if blacklist_entry is None:
            from app.repositories.blacklist_repository import BlacklistRepository
            blacklist_repo = BlacklistRepository(session)
            blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
        await message.answer(
            text,
            reply_markup=main_menu_reply_keyboard(
                user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
            ),
        )
        await state.clear()
    else:
        is_admin = data.get("is_admin", False)
        # Try to get from middleware first
        blacklist_entry = data.get("blacklist_entry")
        if blacklist_entry is None and user:
            from app.repositories.blacklist_repository import BlacklistRepository
            blacklist_repo = BlacklistRepository(session)
            blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
        await message.answer(
            "❌ Ошибка при создании заявки на вывод. Попробуйте позже.",
            reply_markup=main_menu_reply_keyboard(
                user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
            ),
        )
        await state.clear()


async def _show_withdrawal_history(
    message: Message,
    state: FSMContext,
    user: User,
    page: int = 1,
    **data: Any,
) -> None:
    """
    Show withdrawal history with pagination.
    
    R3-14: Supports pagination with navigation buttons.
    
    Args:
        message: Telegram message
        state: FSM context
        user: Current user
        page: Page number (1-indexed)
        **data: Additional data including session_factory
    """
    session_factory = data.get("session_factory")
    
    # Get withdrawal history with SHORT transaction
    if not session_factory:
        # Fallback
        session = data.get("session")
        if not session:
            await message.answer("❌ Системная ошибка. Отправьте /start или обратитесь в поддержку.")
            return
        withdrawal_service = WithdrawalService(session)
        result = await withdrawal_service.get_user_withdrawals(
            user.id, page=page, limit=10
        )
    else:
        # NEW pattern: short read transaction
        async with session_factory() as session:
            async with session.begin():
                withdrawal_service = WithdrawalService(session)
                result = await withdrawal_service.get_user_withdrawals(
                    user.id, page=page, limit=10
                )
        # Transaction closed here

    withdrawals = result["withdrawals"]
    total = result["total"]
    total_pages = result["pages"]
    
    # Save to FSM for navigation
    await state.update_data(withdrawal_page=page)

    # R3-14: Build message text
    if not withdrawals:
        text = "📜 *История выводов*\n\nИстория выводов пуста."
    else:
        text = "📜 *История выводов:*\n\n"
        
        for w in withdrawals:
            status_emoji = {
                "PENDING": "⏳",
                "CONFIRMED": "✅",
                "FAILED": "❌",
            }.get(w.status, "❓")
            
            status_text = {
                "PENDING": "Ожидает",
                "CONFIRMED": "Подтверждено",
                "FAILED": "Отклонено",
            }.get(w.status, "Неизвестно")

            text += (
                f"{status_emoji} *{format_usdt(w.amount)} USDT*\n"
                f"📅 {w.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"📊 Статус: {status_text}\n"
            )

            if w.tx_hash:
                text += f"🔗 Hash: `{w.tx_hash[:16]}...`\n"

            text += "\n"
        
        if total_pages > 1:
            text += f"*Страница {page} из {total_pages}*\n"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=withdrawal_history_keyboard(
            page=page,
            total_pages=total_pages,
            has_withdrawals=len(withdrawals) > 0,
        ),
    )


@router.message(F.text == "📜 История выводов")
async def show_withdrawal_history(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Show withdrawal history (first page).
    
    R3-14: Shows first page of withdrawal history.
    
    Uses session_factory for short read transaction.

    Args:
        message: Telegram message
        state: FSM context
        data: Additional data including session_factory and user
    """
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        return
    
    await _show_withdrawal_history(message, state, user, page=1, **data)


@router.message(F.text.in_({"⬅ Предыдущая страница выводов", "➡ Следующая страница выводов"}))
async def handle_withdrawal_pagination(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Handle pagination for withdrawal history.
    
    R3-14: Navigate between pages.
    
    Args:
        message: Telegram message
        state: FSM context
        **data: Additional data including session_factory and user
    """
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        return
    
    # Get current page from FSM
    state_data = await state.get_data()
    current_page = state_data.get("withdrawal_page", 1)
    
    # Determine direction
    if message.text == "⬅ Предыдущая страница выводов":
        new_page = max(1, current_page - 1)
    else:  # "➡ Следующая страница выводов"
        # Get total pages to check limit
        session_factory = data.get("session_factory")
        if not session_factory:
            session = data.get("session")
            if not session:
                await message.answer("❌ Системная ошибка.")
                return
            withdrawal_service = WithdrawalService(session)
            result = await withdrawal_service.get_user_withdrawals(
                user.id, page=1, limit=10
            )
        else:
            async with session_factory() as session:
                async with session.begin():
                    withdrawal_service = WithdrawalService(session)
                    result = await withdrawal_service.get_user_withdrawals(
                        user.id, page=1, limit=10
                    )
        total_pages = result["pages"]
        new_page = min(total_pages, current_page + 1)
    
    # Show list for new page
    await _show_withdrawal_history(message, state, user, page=new_page, **data)
