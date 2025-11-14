"""
Transaction History Handler
Comprehensive transaction history with filtering and pagination
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TransactionStatus, TransactionType
from app.services.transaction_service import TransactionService
from bot.utils.formatters import format_usdt, format_transaction_hash


router = Router(name="transaction")


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


@router.callback_query(F.data.startswith("transaction_history"))
async def handle_transaction_history(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
) -> None:
    """Handle transaction history main view"""
    transaction_service = TransactionService(session)

    # Parse page number from callback data
    page = 0
    if "_" in callback.data:
        parts = callback.data.split("_")
        if len(parts) > 2 and parts[-1].isdigit():
            page = int(parts[-1])

    limit = 10
    offset = page * limit

    # Get transactions
    result = await transaction_service.get_all_transactions(
        user_id, limit=limit, offset=offset
    )
    transactions = result["transactions"]
    total = result["total"]
    has_more = result["has_more"]

    # Get statistics
    stats = await transaction_service.get_transaction_stats(user_id)

    message = "📊 **История транзакций**\n\n"

    # Display statistics
    message += "**Общая статистика:**\n"
    message += (
        f"💰 Всего депозитов: "
        f"{format_usdt(stats['total_deposits'])} USDT "
        f"({stats['transaction_count']['deposits']} шт.)\n"
    )
    message += (
        f"💸 Всего выведено: "
        f"{format_usdt(stats['total_withdrawals'])} USDT "
        f"({stats['transaction_count']['withdrawals']} шт.)\n"
    )
    message += (
        f"🎁 Реферальных доходов: "
        f"{format_usdt(stats['total_referral_earnings'])} USDT "
        f"({stats['transaction_count']['referral_rewards']} шт.)\n\n"
    )

    if stats.get("pending_withdrawals", 0) > 0 or stats.get(
        "pending_earnings", 0
    ) > 0:
        message += "**В обработке:**\n"
        if stats.get("pending_withdrawals", 0) > 0:
            message += (
                f"⏳ Вывод средств: "
                f"{format_usdt(stats['pending_withdrawals'])} USDT\n"
            )
        if stats.get("pending_earnings", 0) > 0:
            message += (
                f"⏳ Реферальные доходы: "
                f"{format_usdt(stats['pending_earnings'])} USDT\n"
            )
        message += "\n"

    message += "---\n\n"

    # Display transactions
    if not transactions:
        message += "У вас пока нет транзакций."
    else:
        message += (
            f"**Транзакции** ({offset + 1}-"
            f"{offset + len(transactions)} из {total}):\n\n"
        )

        for idx, tx in enumerate(transactions, 1):
            type_emoji = get_transaction_type_emoji(tx["type"])
            status_emoji = get_status_emoji(tx["status"])
            date = tx["created_at"].strftime("%d.%m.%Y %H:%M")

            message += f"{idx}. {type_emoji} **{tx['description']}**\n"
            message += (
                f"   {status_emoji} {get_status_text(tx['status'])} | "
                f"{format_usdt(tx['amount'])} USDT\n"
            )
            message += f"   📅 {date}\n"

            if tx.get("tx_hash") and tx["status"] == TransactionStatus.CONFIRMED:
                short_hash = format_transaction_hash(tx["tx_hash"])
                message += f"   🔗 TX: `{short_hash}`\n"

            message += "\n"

    # Create keyboard with pagination and filters
    buttons = []

    # Filter buttons
    buttons.append(
        [
            InlineKeyboardButton(
                text="💰 Депозиты", callback_data="transaction_filter_deposit"
            ),
            InlineKeyboardButton(
                text="💸 Выводы",
                callback_data="transaction_filter_withdrawal",
            ),
        ]
    )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🎁 Рефералы",
                callback_data="transaction_filter_referral",
            ),
            InlineKeyboardButton(
                text="📊 Все", callback_data="transaction_history"
            ),
        ]
    )

    # Pagination
    if page > 0 or has_more:
        pagination_row = []
        if page > 0:
            pagination_row.append(
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"transaction_history_{page - 1}",
                )
            )
        if has_more:
            pagination_row.append(
                InlineKeyboardButton(
                    text="Вперёд ▶️",
                    callback_data=f"transaction_history_{page + 1}",
                )
            )
        buttons.append(pagination_row)

    # Back button
    buttons.append(
        [
            InlineKeyboardButton(
                text="🏠 Главное меню", callback_data="main_menu"
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        message, parse_mode="Markdown", reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("transaction_filter_"))
async def handle_transaction_history_filter(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
) -> None:
    """Handle transaction history with filter"""
    transaction_service = TransactionService(session)

    # Parse filter type
    filter_type = None
    filter_name = "Все транзакции"

    if callback.data == "transaction_filter_deposit":
        filter_type = TransactionType.DEPOSIT
        filter_name = "Депозиты"
    elif callback.data == "transaction_filter_withdrawal":
        filter_type = TransactionType.WITHDRAWAL
        filter_name = "Выводы средств"
    elif callback.data == "transaction_filter_referral":
        filter_type = TransactionType.REFERRAL_REWARD
        filter_name = "Реферальные доходы"

    limit = 10
    offset = 0

    # Get filtered transactions
    result = await transaction_service.get_all_transactions(
        user_id, limit=limit, offset=offset, transaction_type=filter_type
    )
    transactions = result["transactions"]
    total = result["total"]

    message = f"📊 **{filter_name}**\n\n"

    if not transactions:
        message += f'У вас пока нет транзакций типа "{filter_name}".'
    else:
        message += f"Найдено: **{total}** транзакций\n\n"

        for idx, tx in enumerate(transactions, 1):
            type_emoji = get_transaction_type_emoji(tx["type"])
            status_emoji = get_status_emoji(tx["status"])
            date = tx["created_at"].strftime("%d.%m.%Y %H:%M")

            message += f"{idx}. {type_emoji} **{tx['description']}**\n"
            message += (
                f"   {status_emoji} {get_status_text(tx['status'])} | "
                f"{format_usdt(tx['amount'])} USDT\n"
            )
            message += f"   📅 {date}\n"

            if tx.get("tx_hash") and tx["status"] == TransactionStatus.CONFIRMED:
                short_hash = format_transaction_hash(tx["tx_hash"])
                message += f"   🔗 TX: `{short_hash}`\n"

            message += "\n"

    # Create keyboard
    buttons = [
        [
            InlineKeyboardButton(
                text="◀️ Все транзакции",
                callback_data="transaction_history",
            )
        ],
        [
            InlineKeyboardButton(
                text="🏠 Главное меню", callback_data="main_menu"
            )
        ],
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        message, parse_mode="Markdown", reply_markup=keyboard
    )
    await callback.answer()
