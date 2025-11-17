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

from app.models.user import User
from app.services.user_service import UserService
from app.services.withdrawal_service import WithdrawalService
from bot.keyboards.reply import main_menu_reply_keyboard, withdrawal_keyboard
from bot.states.withdrawal import WithdrawalStates
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
    
    # Check verification status (from TZ: withdrawals require verification)
    if not user.is_verified:
        await message.answer(
            "❌ Для вывода средств необходимо пройти верификацию!\n\n"
            "Используйте кнопку '✅ Пройти верификацию' в настройках.",
            reply_markup=withdrawal_keyboard(),
        )
        return

    session_factory = data.get("session_factory")
    
    # Get balance with SHORT transaction
    if not session_factory:
        # Fallback
        session = data.get("session")
        if not session:
            await message.answer("❌ Системная ошибка")
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
) -> None:
    """
    Withdraw specific amount.

    Args:
        message: Telegram message
        state: FSM state
    """
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
            "❌ Для вывода средств необходимо пройти верификацию!\n\n"
            "Используйте кнопку '✅ Пройти верификацию' в настройках."
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
            await message.answer("❌ Системная ошибка")
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
    
    password = (message.text or "").strip()

    # Delete message with password
    await message.delete()

    session_factory = data.get("session_factory")
    
    # Verify password and create withdrawal with SHORT transaction
    if not session_factory:
        # Fallback
        session = data.get("session")
        if not session:
            await message.answer("❌ Системная ошибка")
            await state.clear()
            return
        
        user_service = UserService(session)
        if not user_service.verify_financial_password(user, password):
            await message.answer(
                "❌ Неверный финансовый пароль!\n\nПопробуйте еще раз:"
            )
            return
        
        # Get amount from state
        state_data = await state.get_data()
        amount = state_data.get("amount")
        
        # Get balance
        balance = await user_service.get_user_balance(user.id)
        
        # Create withdrawal
        withdrawal_service = WithdrawalService(session)
        transaction, error = await withdrawal_service.request_withdrawal(
            user_id=user.id,
            amount=amount,
            available_balance=Decimal(str(balance["available_balance"])),
        )
    else:
        # NEW pattern: short transaction for CRITICAL withdrawal creation
        async with session_factory() as session:
            async with session.begin():
                user_service = UserService(session)
                if not user_service.verify_financial_password(user, password):
                    await message.answer(
                        "❌ Неверный финансовый пароль!\n\nПопробуйте еще раз:"
                    )
                    return
                
                # Get amount from state
                state_data = await state.get_data()
                amount = state_data.get("amount")
                
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

    if error:
        await message.answer(
            f"❌ Ошибка создания заявки:\n{error}",
            reply_markup=main_menu_reply_keyboard(),
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

        await message.answer(text, reply_markup=main_menu_reply_keyboard())
        await state.clear()
    else:
        await message.answer(
            "❌ Ошибка при создании заявки на вывод. Попробуйте позже.",
            reply_markup=main_menu_reply_keyboard(),
        )
        await state.clear()


@router.message(F.text == "📜 История выводов")
async def show_withdrawal_history(
    message: Message,
    **data: Any,
) -> None:
    """
    Show withdrawal history.
    
    Uses session_factory for short read transaction.

    Args:
        message: Telegram message
        data: Additional data including session_factory and user
    """
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        return
    
    session_factory = data.get("session_factory")
    
    # Get withdrawal history with SHORT transaction
    if not session_factory:
        # Fallback
        session = data.get("session")
        if not session:
            await message.answer("❌ Системная ошибка")
            return
        withdrawal_service = WithdrawalService(session)
        result = await withdrawal_service.get_user_withdrawals(
            user.id, page=1, limit=10
        )
    else:
        # NEW pattern: short read transaction
        async with session_factory() as session:
            async with session.begin():
                withdrawal_service = WithdrawalService(session)
                result = await withdrawal_service.get_user_withdrawals(
                    user.id, page=1, limit=10
                )
        # Transaction closed here

    withdrawals = result["withdrawals"]

    if not withdrawals:
        text = "📜 История выводов пуста"
    else:
        text = "📜 *История выводов:*\n\n"
        for w in withdrawals:
            status_emoji = {
                "PENDING": "⏳",
                "CONFIRMED": "✅",
                "FAILED": "❌",
            }.get(w.status, "❓")

            text += (
                f"{status_emoji} *{w.amount} USDT*\n"
                f"📅 {w.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            )

            if w.tx_hash:
                text += f"🔗 Hash: `{w.tx_hash[:16]}...`\n"

            text += "\n"

    await message.answer(
        text, parse_mode="Markdown", reply_markup=withdrawal_keyboard()
    )
