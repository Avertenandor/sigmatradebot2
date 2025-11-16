"""
Transaction History Handler - ТОЛЬКО REPLY KEYBOARDS!

Shows transaction history without inline keyboards.
"""

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TransactionStatus, TransactionType
from app.models.user import User
from app.services.transaction_service import TransactionService
from bot.keyboards.reply import main_menu_reply_keyboard
from bot.utils.formatters import format_transaction_hash, format_usdt

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


@router.message(F.text == "📜 История")
async def handle_transaction_history(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    """Show transaction history (last 20 transactions)."""
    transaction_service = TransactionService(session)

    # Get last 20 transactions
    result = await transaction_service.get_all_transactions(
        user.id, limit=20, offset=0
    )
    transactions = result["transactions"]
    total = result["total"]

    # Get statistics
    stats = await transaction_service.get_transaction_stats(user.id)

    text = "📊 *История транзакций*\n\n"

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
    else:
        text += (
            f"*Последние транзакции* (показано {len(transactions)} "
            f"из {total}):\n\n"
        )

        for idx, tx in enumerate(transactions, 1):
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

    await message.answer(
        text, parse_mode="Markdown", reply_markup=main_menu_reply_keyboard()
    )
