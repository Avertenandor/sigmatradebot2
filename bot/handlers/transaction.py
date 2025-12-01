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
    transaction_history_type_keyboard,
)
from bot.utils.formatters import format_transaction_hash, format_usdt, escape_md
from app.services.report_service import ReportService
from aiogram.types import BufferedInputFile
from datetime import datetime
from loguru import logger

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
    filter_blockchain: bool | None = None,
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
        filter_blockchain: Filter by blockchain (True=only hash, False=only internal)
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
        filter_blockchain=filter_blockchain,
    )
    transactions = result["transactions"]
    total = result["total"]
    has_more = result.get("has_more", False)

    # Get statistics
    stats = await transaction_service.get_transaction_stats(user.id)

    # Build message text
    title = "📊 *История транзакций*"
    if filter_blockchain is not None:
        title = "🔗 *Транзакции в блокчейне*" if filter_blockchain else "🔄 *Внутренние транзакции*"
    
    text = f"{title}\n\n"

    # Display filter info
    if filter_type:
        filter_names = {
            TransactionType.DEPOSIT: "Депозиты",
            TransactionType.WITHDRAWAL: "Выводы",
            TransactionType.REFERRAL_REWARD: "Реферальные",
        }
        text += f"🔍 *Фильтр:* {filter_names.get(filter_type, 'Неизвестно')}\n\n"

    # Display statistics (condensed)
    text += (
        f"💰 Депозиты: *{format_usdt(stats['total_deposits'])}* | "
        f"💸 Выводы: *{format_usdt(stats['total_withdrawals'])}*\n"
        f"🎁 Реферальные: *{format_usdt(stats['total_referral_earnings'])}*\n\n"
    )

    text += "---\n\n"

    # Display transactions
    if not transactions:
        text += "У вас пока нет транзакций в этой категории."
    else:
        start_num = offset + 1
        end_num = offset + len(transactions)
        text += (
            f"*Транзакции* (показано {start_num}-{end_num} из {total}):\n\n"
        )

        for idx, tx in enumerate(transactions, start_num):
            type_emoji = get_transaction_type_emoji(tx.type)
            status_emoji = get_status_emoji(tx.status)
            date = tx.created_at.strftime("%d.%m.%Y %H:%M")
            
            # Extract ID from composite ID if possible, or use full ID
            tx_id_display = tx.id.split(':')[1] if ':' in tx.id else tx.id
            
            description = escape_md(tx.description)

            text += f"{idx}. {type_emoji} *{description}* (ID: `{tx_id_display}`)\n"
            text += (
                f"   {status_emoji} {get_status_text(tx.status)} | "
                f"*{format_usdt(tx.amount)} USDT*\n"
            )
            text += f"   📅 {date}\n"

            if tx.tx_hash:
                short_hash = format_transaction_hash(tx.tx_hash)
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
        filter_blockchain=filter_blockchain,
    )

    # Build keyboard
    has_prev = page > 0
    keyboard = transaction_history_keyboard(
        current_filter=filter_type.value if filter_type else "all",
        has_prev=has_prev,
        has_next=has_more,
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


@router.message(F.text == "📜 История операций")
@router.message(F.text == "📜 История")  # Backward compatibility
async def handle_transaction_history_menu(
    message: Message,
    state: FSMContext,
) -> None:
    """Show transaction history menu."""
    await message.answer(
        "Выберите тип транзакций:",
        reply_markup=transaction_history_type_keyboard(),
    )


@router.message(F.text == "🔄 Внутренние транзакции")
async def handle_internal_transactions(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show internal transactions."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return

    # Reset to first page, no type filter, INTERNAL only
    safe_data = {k: v for k, v in data.items() if k not in ('user', 'state', 'session')}
    await _show_transaction_history(
        message, session, state, user, 
        filter_type=None, 
        page=0, 
        filter_blockchain=False,
        **safe_data
    )


@router.message(F.text == "🔗 Транзакции в блокчейне")
async def handle_blockchain_transactions(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show blockchain transactions."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return

    # Reset to first page, no type filter, BLOCKCHAIN only
    safe_data = {k: v for k, v in data.items() if k not in ('user', 'state', 'session')}
    await _show_transaction_history(
        message, session, state, user, 
        filter_type=None, 
        page=0, 
        filter_blockchain=True,
        **safe_data
    )


@router.message(F.text == "📊 Все транзакции")
async def handle_all_transactions(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show all transactions (reset filter, keep view mode)."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return

    # Get current view mode
    state_data = await state.get_data()
    filter_blockchain = state_data.get("filter_blockchain")

    safe_data = {k: v for k, v in data.items() if k not in ('user', 'state', 'session')}
    await _show_transaction_history(
        message, session, state, user, 
        filter_type=None, 
        page=0, 
        filter_blockchain=filter_blockchain,
        **safe_data
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

    # Get current view mode
    state_data = await state.get_data()
    filter_blockchain = state_data.get("filter_blockchain")

    # Map button text to transaction type
    filter_map = {
        "💰 Депозиты": TransactionType.DEPOSIT,
        "💸 Выводы": TransactionType.WITHDRAWAL,
        "🎁 Реферальные": TransactionType.REFERRAL_REWARD,
    }

    filter_type = filter_map.get(message.text)
    
    safe_data = {k: v for k, v in data.items() if k not in ('user', 'state', 'session')}
    await _show_transaction_history(
        message, session, state, user, 
        filter_type=filter_type, 
        page=0, 
        filter_blockchain=filter_blockchain,
        **safe_data
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

    # Get current state
    state_data = await state.get_data()
    current_filter_str = state_data.get("transaction_filter")
    current_page = state_data.get("transaction_page", 0)
    filter_blockchain = state_data.get("filter_blockchain")

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

    safe_data = {k: v for k, v in data.items() if k not in ('user', 'state', 'session')}
    await _show_transaction_history(
        message,
        session,
        state,
        user,
        filter_type=filter_type,
        page=new_page,
        filter_blockchain=filter_blockchain,
        **safe_data,
    )


@router.message(F.text == "📥 Скачать отчет (Excel)")
async def handle_export_report(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Handle Excel report export."""
    user: User | None = data.get("user")
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return

    wait_msg = await message.answer("⏳ Генерирую отчет... Пожалуйста, подождите.")
    await message.bot.send_chat_action(message.chat.id, "upload_document")

    try:
        report_service = ReportService(session)
        # Generate report
        report_bytes = await report_service.generate_user_report(user.id)
        
        # Send file
        filename = f"SigmaTrade_Report_{user.telegram_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        input_file = BufferedInputFile(report_bytes, filename=filename)
        
        await message.answer_document(
            document=input_file,
            caption="📊 Ваш полный отчет (транзакции, депозиты, рефералы)",
        )
        await wait_msg.delete()
        
    except Exception as e:
        logger.exception(f"Failed to generate report for user {user.id}: {e}")
        await wait_msg.edit_text("❌ Произошла ошибка при генерации отчета. Обратитесь в поддержку.")
