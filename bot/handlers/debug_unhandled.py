"""
Debug handler for unhandled messages.

Catches all messages that don't match any handler to help debug routing issues.
"""

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import Message
from loguru import logger

router = Router()


@router.message(StateFilter('*'))
async def debug_unhandled(message: Message):
    """
    Catch-all handler for debugging.
    
    This should be registered LAST to catch messages that don't match any other handler.
    """
    text_bytes = message.text.encode('utf-8') if message.text else b''
    logger.warning(
        f"UNHANDLED MESSAGE: user={message.from_user.id if message.from_user else None} "
        f"text={message.text!r} "
        f"bytes={text_bytes.hex()} "
        f"chat_id={message.chat.id}"
    )
    
    # Don't send response to avoid spam, just log

