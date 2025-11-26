"""
Fallback handlers for orphaned states.

Handles buttons like "✅ Yes", "❌ No" when the FSM state has been lost
(e.g. due to restart or timeout), preventing "Unhandled message" logs
and user confusion.
"""

from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardRemove

from bot.keyboards.reply import main_menu_reply_keyboard
from bot.utils.menu_buttons import CONFIRMATION_BUTTONS

router = Router()


@router.message(F.text.in_(CONFIRMATION_BUTTONS))
async def handle_orphaned_confirmation(message: Message, **data) -> None:
    """
    Handle confirmation buttons when no FSM state is active.
    
    This happens if the bot was restarted or state was cleared, 
    but the user still has the confirmation keyboard open.
    """
    # Get is_admin from middleware data to ensure admin button is shown
    is_admin = data.get("is_admin", False)
    
    await message.answer(
        "⚠️ **Действие отменено или устарело**\n\n"
        "Состояние диалога было сброшено (возможно, из-за обновления бота). "
        "Пожалуйста, начните действие заново через меню.",
        parse_mode="Markdown",
        reply_markup=main_menu_reply_keyboard(
            user=message.from_user,
            is_admin=is_admin
        )
    )


@router.message(F.text.in_(["25%", "50%", "MAX"]))
async def handle_orphaned_wallet_buttons(message: Message) -> None:
    """Handle wallet quick amount buttons when state is lost."""
    await message.answer(
        "⚠️ **Действие устарело**\n\n"
        "Пожалуйста, вернитесь в меню управления кошельком.",
        parse_mode="Markdown",
        # Don't send keyboard here, let them use existing or /start
    )

