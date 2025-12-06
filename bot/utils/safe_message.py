"""
Safe Message Utilities
Provides safe wrappers for Telegram message sending with automatic Markdown fallback.
"""

import logging
from typing import Any

from aiogram.types import Message
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


async def safe_answer(
    message: Message,
    text: str,
    parse_mode: str | None = "Markdown",
    reply_markup: Any = None,
    **kwargs
) -> Message:
    """
    Safely send answer to message with automatic retry without Markdown on error.

    Args:
        message: Original message to answer
        text: Text to send
        parse_mode: Parse mode (Markdown, MarkdownV2, HTML)
        reply_markup: Optional keyboard markup
        **kwargs: Additional arguments for message.answer()

    Returns:
        Sent message
    """
    try:
        return await message.answer(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs
        )
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower() or "parse" in str(e).lower():
            logger.warning(f"Markdown parse error, retrying without parse_mode: {e}")
            return await message.answer(
                text,
                parse_mode=None,
                reply_markup=reply_markup,
                **kwargs
            )
        raise


async def safe_send_message(
    bot: Bot,
    chat_id: int | str,
    text: str,
    parse_mode: str | None = "Markdown",
    reply_markup: Any = None,
    **kwargs
) -> Message:
    """
    Safely send message to chat with automatic retry without Markdown on error.

    Args:
        bot: Bot instance
        chat_id: Target chat ID
        text: Text to send
        parse_mode: Parse mode (Markdown, MarkdownV2, HTML)
        reply_markup: Optional keyboard markup
        **kwargs: Additional arguments for bot.send_message()

    Returns:
        Sent message
    """
    try:
        return await bot.send_message(
            chat_id,
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs
        )
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower() or "parse" in str(e).lower():
            logger.warning(f"Markdown parse error, retrying without parse_mode: {e}")
            return await bot.send_message(
                chat_id,
                text,
                parse_mode=None,
                reply_markup=reply_markup,
                **kwargs
            )
        raise


async def safe_edit_text(
    message: Message,
    text: str,
    parse_mode: str | None = "Markdown",
    reply_markup: Any = None,
    **kwargs
) -> Message | bool:
    """
    Safely edit message text with automatic retry without Markdown on error.

    Args:
        message: Message to edit
        text: New text
        parse_mode: Parse mode (Markdown, MarkdownV2, HTML)
        reply_markup: Optional keyboard markup
        **kwargs: Additional arguments for message.edit_text()

    Returns:
        Edited message or True
    """
    try:
        return await message.edit_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs
        )
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower() or "parse" in str(e).lower():
            logger.warning(f"Markdown parse error, retrying without parse_mode: {e}")
            return await message.edit_text(
                text,
                parse_mode=None,
                reply_markup=reply_markup,
                **kwargs
            )
        raise


async def safe_reply(
    message: Message,
    text: str,
    parse_mode: str | None = "Markdown",
    reply_markup: Any = None,
    **kwargs
) -> Message:
    """
    Safely reply to message with automatic retry without Markdown on error.

    Args:
        message: Message to reply to
        text: Text to send
        parse_mode: Parse mode (Markdown, MarkdownV2, HTML)
        reply_markup: Optional keyboard markup
        **kwargs: Additional arguments for message.reply()

    Returns:
        Sent message
    """
    try:
        return await message.reply(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs
        )
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower() or "parse" in str(e).lower():
            logger.warning(f"Markdown parse error, retrying without parse_mode: {e}")
            return await message.reply(
                text,
                parse_mode=None,
                reply_markup=reply_markup,
                **kwargs
            )
        raise
