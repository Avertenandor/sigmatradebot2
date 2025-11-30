"""
Withdrawal handlers.

Handles withdrawal requests and history viewing.
"""

import asyncio
from decimal import Decimal
from typing import Any

from aiogram import F, Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.transaction import Transaction # For auto-payout
from app.models.enums import TransactionStatus # For auto-payout
from app.services.user_service import UserService
from app.services.withdrawal_service import WithdrawalService
from bot.keyboards.reply import (
    finpass_input_keyboard,
    main_menu_reply_keyboard,
    withdrawal_keyboard,
)
from bot.states.withdrawal import WithdrawalStates
from bot.utils.menu_buttons import is_menu_button

router = Router()


async def process_auto_payout(
    tx_id: int, 
    amount: Decimal, 
    to_address: str, 
    bot: Bot, 
    telegram_id: int
):
    """
    Process auto-payout in background.
    """
    from app.config.database import async_session_maker
    from app.services.blockchain_service import get_blockchain_service
    
    blockchain_service = get_blockchain_service()
    if not blockchain_service:
        logger.error(f"Blockchain service not initialized for auto-payout tx {tx_id}")
        return

    logger.info(f"Starting auto-payout for tx {tx_id}, amount {amount} to {to_address}")
    
    # Send payment
    result = await blockchain_service.send_payment(to_address, float(amount))
    
    async with async_session_maker() as session:
        stmt = select(Transaction).where(Transaction.id == tx_id)
        res = await session.execute(stmt)
        tx = res.scalar_one_or_none()
        
        if not tx:
            logger.error(f"Transaction {tx_id} not found during auto-payout update")
            return

        if result["success"]:
            logger.info(f"Auto-payout successful for tx {tx_id}: {result['tx_hash']}")
            tx.tx_hash = result["tx_hash"]
            tx.status = TransactionStatus.CONFIRMED.value
            
            # Notify user about success
            try:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=(
                        f"✅ *Выплата отправлена!*\n\n"
                        f"💰 Сумма: `{amount} USDT`\n"
                        f"💳 Кошелек: `{to_address[:6]}...{to_address[-4:]}`\n"
                        f"🔗 TX: [Посмотреть транзакцию](https://bscscan.com/tx/{result['tx_hash']})\n\n"
                        f"🤝 Спасибо за ваше доверие к SigmaTrade!"
                    ),
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(f"Failed to send auto-payout notification to {telegram_id}: {e}")
                
        else:
            logger.error(f"Auto-payout failed for tx {tx_id}: {result.get('error')}")
            # Revert to PENDING for manual admin review
            tx.status = TransactionStatus.PENDING.value
            
        await session.commit()


@router.message(F.text == "💸 Вывести средства")
async def show_withdrawal_menu(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show withdrawal menu."""
    await state.clear()

    session = data.get("session")
    min_amount = "0.20"  # Default fallback
    
    if session:
        try:
            withdrawal_service = WithdrawalService(session)
            min_val = await withdrawal_service.get_min_withdrawal_amount()
            min_amount = f"{min_val:.2f}"
        except Exception:
            pass

    text = (
        f"💸 *Вывод средств*\n\n"
        f"ℹ️ Вывод возможен по накоплению *{min_amount} USDT* прибыли.\n"
        f"_Это сделано, чтобы не нагружать выплатную систему, "
        f"а также не переплачивать комиссии за транзакции._\n\n"
        f"Выберите действие:"
    )

    await message.answer(
        text,
        reply_markup=withdrawal_keyboard(),
        parse_mode="Markdown",
    )


@router.message(F.text == "💳 Вывести всё")
async def withdraw_all(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle 'Withdraw All' button."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        return

    # Check verification status
    if not user.is_verified:
        await message.answer(
            "❌ Вывод недоступен до верификации!\n\n"
            "Для вывода средств необходимо пройти верификацию.\n"
            "Сначала нажмите '✅ Пройти верификацию' в главном меню.",
            reply_markup=withdrawal_keyboard(),
        )
        return

    session = data.get("session")
    if not session:
        await message.answer("❌ Системная ошибка")
        return
        
    user_service = UserService(session)
    balance = await user_service.get_user_balance(user.id)
    amount = Decimal(str(balance["available_balance"]))

    # Check minimum
    withdrawal_service = WithdrawalService(session)
    min_amount = await withdrawal_service.get_min_withdrawal_amount()
    
    if amount < min_amount:
        await message.answer(
            f"❌ Недостаточно средств для вывода!\n\n"
            f"Минимальная сумма: {min_amount} USDT\n"
            f"Ваш баланс: {amount:.2f} USDT",
            reply_markup=withdrawal_keyboard(),
        )
        return

    # Save amount and ask for CONFIRMATION first (convert Decimal to str for JSON)
    await state.update_data(amount=str(amount))
    await state.set_state(WithdrawalStates.waiting_for_confirmation)

    text = (
        f"⚠️ *Подтверждение вывода*\n\n"
        f"💰 Сумма: *{amount:.2f} USDT*\n"
        f"💳 Кошелёк: `{user.wallet_address[:10]}...{user.wallet_address[-6:]}`\n\n"
        f"❗️ Убедитесь, что это ваш *ЛИЧНЫЙ* кошелёк (не биржевой)!\n\n"
        f"Для подтверждения напишите: *да* или *yes*\n"
        f"Для отмены: *нет* или *отмена*"
    )

    await message.answer(text, parse_mode="Markdown")


@router.message(WithdrawalStates.waiting_for_confirmation)
async def confirm_withdrawal(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle withdrawal confirmation."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    # Check for menu button
    if is_menu_button(message.text or ""):
        await state.clear()
        return

    answer = (message.text or "").strip().lower()
    
    if answer in ("да", "yes", "д", "y"):
        # Confirmed - ask for password
        state_data = await state.get_data()
        amount = state_data.get("amount")
        
        text = (
            f"💸 *Вывод средств*\n\n"
            f"Сумма к выводу: *{amount} USDT*\n\n"
            f"🔐 Введите ваш финансовый пароль:"
        )

        await message.answer(text, reply_markup=finpass_input_keyboard(), parse_mode="Markdown")
        await state.set_state(WithdrawalStates.waiting_for_financial_password)
    
    elif answer in ("нет", "no", "н", "n", "отмена", "cancel"):
        await state.clear()
        await message.answer(
            "❌ Вывод отменён.",
            reply_markup=withdrawal_keyboard(),
        )
    
    else:
        await message.answer(
            "⚠️ Напишите *да* для подтверждения или *нет* для отмены.",
            parse_mode="Markdown",
        )


@router.message(F.text == "💵 Вывести указанную сумму")
async def withdraw_amount(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle 'Withdraw Amount' button."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        return

    # Check verification status
    if not user.is_verified:
        await message.answer(
            "❌ Вывод недоступен до верификации!\n\n"
            "Для вывода средств необходимо пройти верификацию.\n"
            "Сначала нажмите '✅ Пройти верификацию' в главном меню.",
            reply_markup=withdrawal_keyboard(),
        )
        return

    session = data.get("session")
    if not session:
        await message.answer("❌ Системная ошибка")
        return

    withdrawal_service = WithdrawalService(session)
    min_amount = await withdrawal_service.get_min_withdrawal_amount()

    await message.answer(
        f"Введите сумму для вывода (мин. {min_amount} USDT):",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(WithdrawalStates.waiting_for_amount)


@router.message(WithdrawalStates.waiting_for_amount)
async def process_withdrawal_amount(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Process withdrawal amount."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    # Check verification status
    if not user.is_verified:
        await message.answer(
            "❌ Вывод недоступен до верификации!\n\n"
            "Для вывода средств необходимо пройти верификацию.\n"
            "Сначала нажмите '✅ Пройти верификацию' в главном меню.",
            reply_markup=withdrawal_keyboard(),
        )
        await state.clear()
        return

    if is_menu_button(message.text or ""):
        await state.clear()
        return

    try:
        amount = Decimal((message.text or "").strip())
    except (ValueError, ArithmeticError):
        await message.answer(
            "❌ Неверный формат суммы!\n\n"
            "Введите число, например: 100.50"
        )
        return

    # Check minimum
    session = data.get("session")
    if not session:
        await message.answer("❌ Системная ошибка")
        return
        
    withdrawal_service = WithdrawalService(session)
    min_amount = await withdrawal_service.get_min_withdrawal_amount()

    if amount < min_amount:
        await message.answer(
            f"❌ Сумма слишком маленькая!\n\n"
            f"Минимальная сумма: {min_amount} USDT\n"
            f"Попробуйте еще раз:"
        )
        return

    session_factory = data.get("session_factory")
    
    if not session_factory:
        user_service = UserService(session)
        balance = await user_service.get_user_balance(user.id)
    else:
        async with session_factory() as temp_session:
            async with temp_session.begin():
                user_service = UserService(temp_session)
                balance = await user_service.get_user_balance(user.id)

    if not balance or Decimal(str(balance["available_balance"])) < amount:
        await message.answer(
            f"❌ Недостаточно средств!\n\n"
            f"Доступно: {balance['available_balance']:.2f} USDT\n"
            f"Попробуйте меньшую сумму:"
        )
        return

    # Convert Decimal to str for JSON serialization in FSM state
    await state.update_data(amount=str(amount))

    text = (
        f"💸 *Вывод средств*\n\n"
        f"Сумма: *{amount} USDT*\n\n"
        f"🔐 Введите ваш финансовый пароль:"
    )

    await message.answer(text, reply_markup=finpass_input_keyboard(), parse_mode="Markdown")
    await state.set_state(WithdrawalStates.waiting_for_financial_password)


@router.message(WithdrawalStates.waiting_for_financial_password)
async def process_financial_password(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Process financial password and create withdrawal."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    # Handle cancel button
    if (message.text or "").strip() == "❌ Отменить вывод":
        await state.clear()
        await message.answer(
            "❌ Вывод отменён.",
            reply_markup=withdrawal_keyboard(),
        )
        return
    
    if is_menu_button(message.text or ""):
        await state.clear()
        return
    
    # Check rate limit
    telegram_id = message.from_user.id if message.from_user else None
    if telegram_id:
        from bot.utils.operation_rate_limit import OperationRateLimiter
        redis_client = data.get("redis_client")
        rate_limiter = OperationRateLimiter(redis_client=redis_client)
        allowed, error_msg = await rate_limiter.check_withdrawal_limit(telegram_id)
        if not allowed:
            await message.answer(
                error_msg or "Слишком много заявок на вывод",
                reply_markup=withdrawal_keyboard(),
            )
            await state.clear()
            return
    
    password = (message.text or "").strip()

    try:
        await message.delete()
    except Exception:
        pass

    session_factory = data.get("session_factory")
    
    # Verify password and create withdrawal
    if not session_factory:
        await message.answer("❌ Системная ошибка (no session factory)")
        return
        
    try:
        transaction = None
        error = None
        is_auto = False
        no_finpass = False
        
        async with session_factory() as session:
            user_service = UserService(session)
            # Re-check user (detached)
            current_user = await user_service.get_by_id(user.id)
            if not current_user:
                raise ValueError("User not found")
            
            # Check password
            if not current_user.financial_password:
                no_finpass = True
            else:
                # Verify password with rate limiting
                is_valid, rate_error = await user_service.verify_financial_password(
                    current_user.id, password
                )
                if not is_valid:
                    error = rate_error or "Неверный финансовый пароль"
                else:
                    # Proceed
                    state_data = await state.get_data()
                    amount = Decimal(str(state_data.get("amount")))
                    
                    balance = await user_service.get_user_balance(current_user.id)
                    
                    withdrawal_service = WithdrawalService(session)
                    transaction, error, is_auto = await withdrawal_service.request_withdrawal(
                        user_id=current_user.id,
                        amount=amount,
                        available_balance=Decimal(str(balance["available_balance"])),
                    )
        
        # Outside session - send messages
        if no_finpass:
            await message.answer(
                "❌ Финансовый пароль не установлен!",
                reply_markup=main_menu_reply_keyboard(user=user)
            )
        elif error:
            await message.answer(
                f"❌ {error}",
                reply_markup=withdrawal_keyboard(),
            )
        elif transaction:
            if is_auto:
                await message.answer(
                    f"✅ *Заявка #{transaction.id} принята!*\n\n"
                    f"💰 Сумма: *{transaction.amount} USDT*\n"
                    f"💳 Кошелек: `{transaction.to_address[:10]}...{transaction.to_address[-6:]}`\n\n"
                    f"⚡️ *Автоматическая выплата одобрена*\n"
                    f"Средства поступят в течение 1-5 минут.\n\n"
                    f"📊 Статус: '📜 История выводов'",
                    parse_mode="Markdown",
                    reply_markup=main_menu_reply_keyboard(user=user)
                )
                # Trigger background task
                asyncio.create_task(
                    process_auto_payout(
                        transaction.id, 
                        transaction.amount, 
                        transaction.to_address,
                        message.bot,
                        user.telegram_id
                    )
                )
            else:
                await message.answer(
                    f"✅ *Заявка #{transaction.id} создана!*\n\n"
                    f"💰 Сумма: *{transaction.amount} USDT*\n"
                    f"💳 Кошелек: `{transaction.to_address[:10]}...{transaction.to_address[-6:]}`\n\n"
                    f"⏱ *Время обработки:* до 24 часов\n"
                    f"📊 Статус можно проверить в '📜 История выводов'",
                    parse_mode="Markdown",
                    reply_markup=main_menu_reply_keyboard(user=user)
                )
        else:
            await message.answer(
                "❌ Неизвестная ошибка",
                reply_markup=withdrawal_keyboard(),
            )

    except Exception as e:
        logger.error(f"Error processing withdrawal: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при обработке заявки",
            reply_markup=withdrawal_keyboard(),
        )
    
    await state.clear()


@router.message(F.text == "📜 История выводов")
async def show_history(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show withdrawal history."""
    user: User | None = data.get("user")
    if not user:
        return
        
    await _show_withdrawal_history(message, state, user, page=1, **data)


async def _show_withdrawal_history(
    message: Message,
    state: FSMContext,
    user: User,
    page: int = 1,
    **data: Any,
) -> None:
    """Show withdrawal history with pagination."""
    session_factory = data.get("session_factory")
    
    if not session_factory:
        session = data.get("session")
        if not session:
            await message.answer("❌ Системная ошибка.")
            return
        withdrawal_service = WithdrawalService(session)
        result = await withdrawal_service.get_user_withdrawals(
            user.id, page=page, limit=10
        )
    else:
        async with session_factory() as session:
            async with session.begin():
                withdrawal_service = WithdrawalService(session)
                result = await withdrawal_service.get_user_withdrawals(
                    user.id, page=page, limit=10
                )

    withdrawals = result["withdrawals"]
    total = result["total"]
    total_pages = result["pages"]
    
    await state.update_data(withdrawal_page=page)

    if not withdrawals:
        await message.answer("📜 История выводов пуста")
        return

    text = f"📜 *История выводов* (Страница {page}/{total_pages})\n\n"
    
    for tx in withdrawals:
        status_icon = {
            "PENDING": "⏳",
            "PROCESSING": "⚙️",
            "COMPLETED": "✅",
            "FAILED": "❌",
            "REJECTED": "🚫"
        }.get(tx.status, "❓")
        
        date = tx.created_at.strftime("%d.%m.%Y %H:%M")
        text += f"{status_icon} *{tx.amount} USDT* | {date}\n"
        text += f"ID: `{tx.id}`\n"
        if tx.tx_hash:
            text += f"🔗 [BscScan](https://bscscan.com/tx/{tx.tx_hash})\n"
        text += "───────────────────\n"

    # Pagination keyboard would go here (omitted for brevity, assume simple list)
    await message.answer(text, parse_mode="Markdown")
