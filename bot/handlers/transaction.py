"""
Transaction History Handler - ТОЛЬКО REPLY KEYBOARDS!

Shows transaction history without inline keyboards.
Supports pagination and filtering by transaction type.
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TransactionStatus, TransactionType
from app.models.user import User
from app.services.transaction_service import TransactionService
from bot.keyboards.reply import (
    main_menu_reply_keyboard,
    transaction_history_keyboard,
)
from bot.utils.formatters import format_transaction_hash, format_usdt

router = Router(name="transaction")

# Constants for pagination
TRANSACTIONS_PER_PAGE = 10


def get_transaction_type_emoji(transaction_type: TransactionType) -> str:
    """Get emoji for transaction type"""
    emoji_map = {
        TransactionType.DEPOSIT: "💰",
        TransactionType.WITHDRAWAL: "💸",
        TransactionType.REFERRAL_REWARD: "🎁",
        TransactionType.SYSTEM_PAYOUT: "💵",
        TransactionType.ADJUSTMENT: "📝",
    }
    return emoji_map.get(transaction_type, "📝")


def get_status_emoji(status: TransactionStatus) -> str:
    """Get emoji for transaction status"""
    emoji_map = {
        TransactionStatus.CONFIRMED: "✅",
        TransactionStatus.PENDING: "⏳",
        TransactionStatus.FAILED: "❌",
    }
    return emoji_map.get(status, "❓")


def get_status_text(status: TransactionStatus) -> str:
    """Get text for transaction status"""
    text_map = {
        TransactionStatus.CONFIRMED: "Подтверждено",
        TransactionStatus.PENDING: "В обработке",
        TransactionStatus.FAILED: "Отклонено",
    }
    return text_map.get(status, "Неизвестно")


async def _show_transaction_history(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    user: User,
    filter_type: TransactionType | None = None,
    page: int = 0,
    **data: Any,
) -> None:
    """
    Show transaction history with pagination and filtering.

    Args:
        message: Telegram message
        session: Database session
        state: FSM state
        user: Current user
        filter_type: Transaction type filter (None = all)
        page: Page number (0-based)
        **data: Additional handler data
    """
    transaction_service = TransactionService(session)

    # Calculate offset
    offset = page * TRANSACTIONS_PER_PAGE

    # Get transactions with filter and pagination
    result = await transaction_service.get_all_transactions(
        user.id,
        limit=TRANSACTIONS_PER_PAGE,
        offset=offset,
        transaction_type=filter_type,
    )
    transactions = result["transactions"]
    total = result["total"]
    has_more = result.get("has_more", False)

    # Get statistics
    stats = await transaction_service.get_transaction_stats(user.id)

    # Build message text
    text = "📊 *История транзакций*\n\n"

    # Display filter info
    if filter_type:
        filter_names = {
            TransactionType.DEPOSIT: "Депозиты",
            TransactionType.WITHDRAWAL: "Выводы",
            TransactionType.REFERRAL_REWARD: "Реферальные",
        }
        text += f"🔍 *Фильтр:* {filter_names.get(filter_type, 'Неизвестно')}\n\n"

    # Display statistics
    text += "*Общая статистика:*\n"
    text += (
        f"💰 Всего депозитов: "
        f"*{format_usdt(stats['total_deposits'])} USDT* "
        f"({stats['transaction_count']['deposits']} шт.)\n"
    )
    text += (
        f"💸 Всего выведено: "
        f"*{format_usdt(stats['total_withdrawals'])} USDT* "
        f"({stats['transaction_count']['withdrawals']} шт.)\n"
    )
    text += (
        f"🎁 Реферальных доходов: "
        f"*{format_usdt(stats['total_referral_earnings'])} USDT* "
        f"({stats['transaction_count']['referral_rewards']} шт.)\n\n"
    )

    if (
        stats.get("pending_withdrawals", 0) > 0
        or stats.get("pending_earnings", 0) > 0
    ):
        text += "*В обработке:*\n"
        if stats.get("pending_withdrawals", 0) > 0:
            text += (
                f"⏳ Вывод средств: "
                f"*{format_usdt(stats['pending_withdrawals'])} USDT*\n"
            )
        if stats.get("pending_earnings", 0) > 0:
            text += (
                f"⏳ Реферальные доходы: "
                f"*{format_usdt(stats['pending_earnings'])} USDT*\n"
            )
        text += "\n"

    text += "---\n\n"

    # Display transactions
    if not transactions:
        text += "У вас пока нет транзакций."
        if filter_type:
            text += f"\n\nПопробуйте выбрать другой фильтр или '📊 Все транзакции'."
    else:
        start_num = offset + 1
        end_num = offset + len(transactions)
        text += (
            f"*Транзакции* (показано {start_num}-{end_num} из {total}):\n\n"
        )

        for idx, tx in enumerate(transactions, start_num):
            type_emoji = get_transaction_type_emoji(tx["type"])
            status_emoji = get_status_emoji(tx["status"])
            date = tx["created_at"].strftime("%d.%m.%Y %H:%M")

            text += f"{idx}. {type_emoji} *{tx['description']}*\n"
            text += (
                f"   {status_emoji} {get_status_text(tx['status'])} | "
                f"*{format_usdt(tx['amount'])} USDT*\n"
            )
            text += f"   📅 {date}\n"

            if (
                tx.get("tx_hash")
                and tx["status"] == TransactionStatus.CONFIRMED
            ):
                short_hash = format_transaction_hash(tx["tx_hash"])
                text += f"   🔗 TX: `{short_hash}`\n"

            text += "\n"

        # Show page info
        total_pages = (total + TRANSACTIONS_PER_PAGE - 1) // TRANSACTIONS_PER_PAGE
        if total_pages > 1:
            text += f"\n📄 Страница {page + 1} из {total_pages}\n"

    # Save current filter and page to FSM state
    await state.update_data(
        transaction_filter=filter_type.value if filter_type else None,
        transaction_page=page,
    )

    # Build keyboard
    has_prev = page > 0
    keyboard = transaction_history_keyboard(
        current_filter=filter_type.value if filter_type else "all",
        has_prev=has_prev,
        has_next=has_more,
    )

    is_admin = data.get("is_admin", False)
    from app.repositories.blacklist_repository import BlacklistRepository
    blacklist_repo = BlacklistRepository(session)
    blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


@router.message(F.text == "📜 История")
async def handle_transaction_history(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show transaction history (first page, all transactions)."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return

    # Reset to first page, all transactions
    await _show_transaction_history(
        message, session, state, user, filter_type=None, page=0, **data
    )


@router.message(F.text == "📊 Все транзакции")
async def handle_all_transactions(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show all transactions (reset filter)."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return

    # Reset to first page, all transactions
    await _show_transaction_history(
        message, session, state, user, filter_type=None, page=0, **data
    )


@router.message(F.text.in_(["💰 Депозиты", "💸 Выводы", "🎁 Реферальные"]))
async def handle_transaction_filter(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle transaction type filter."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return

    # Map button text to transaction type
    filter_map = {
        "💰 Депозиты": TransactionType.DEPOSIT,
        "💸 Выводы": TransactionType.WITHDRAWAL,
        "🎁 Реферальные": TransactionType.REFERRAL_REWARD,
    }

    filter_type = filter_map.get(message.text)
    if not filter_type:
        await message.answer("Ошибка: неизвестный фильтр")
        return

    # Reset to first page with new filter
    await _show_transaction_history(
        message, session, state, user, filter_type=filter_type, page=0, **data
    )


@router.message(F.text.in_(["⬅ Предыдущая страница", "➡ Следующая страница"]))
async def handle_transaction_pagination(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle transaction history pagination."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return

    # Get current filter and page from state
    state_data = await state.get_data()
    current_filter_str = state_data.get("transaction_filter")
    current_page = state_data.get("transaction_page", 0)

    # Parse filter
    filter_type = None
    if current_filter_str:
        try:
            filter_type = TransactionType(current_filter_str)
        except ValueError:
            filter_type = None

    # Calculate new page
    if message.text == "⬅ Предыдущая страница":
        new_page = max(0, current_page - 1)
    else:  # "➡ Следующая страница"
        new_page = current_page + 1

    await _show_transaction_history(
        message,
        session,
        state,
        user,
        filter_type=filter_type,
        page=new_page,
        **data,
    )
