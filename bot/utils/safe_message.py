"""
Safe Message Sending Utilities.

Provides robust message sending with automatic Markdown error handling.
"""

from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    ForceReply,
)
from loguru import logger

from bot.utils.formatters import escape_md


async def safe_answer(
    message: Message,
    text: str,
    parse_mode: str | None = "Markdown",
    reply_markup: InlineKeyboardMarkup
    | ReplyKeyboardMarkup
    | ReplyKeyboardRemove
    | ForceReply
    | None = None,
    **kwargs: Any,
) -> Message | None:
    """
    Safely send a message with automatic Markdown error recovery.

    Strategy:
    1. Try to send with specified parse_mode
    2. If Markdown parsing fails, retry without parse_mode
    3. Log the error for debugging

    Args:
        message: Original message to reply to
        text: Message text
        parse_mode: Parse mode (Markdown, MarkdownV2, HTML, None)
        reply_markup: Optional keyboard markup
        **kwargs: Additional arguments for message.answer()

    Returns:
        Sent message or None if all attempts failed
    """
    try:
        return await message.answer(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs,
        )
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e):
            logger.warning(
                f"Markdown parsing failed, retrying without parse_mode: {e}",
                extra={
                    "user_id": message.from_user.id if message.from_user else None,
                    "text_length": len(text),
                    "parse_mode": parse_mode,
                },
            )
            try:
                # Retry without parse_mode
                return await message.answer(
                    text,
                    parse_mode=None,
                    reply_markup=reply_markup,
                    **kwargs,
                )
            except Exception as retry_error:
                logger.error(
                    f"Failed to send message even without parse_mode: {retry_error}",
                    extra={"user_id": message.from_user.id if message.from_user else None},
                )
                return None
        else:
            # Re-raise other TelegramBadRequest errors
            raise
    except Exception as e:
        logger.error(
            f"Unexpected error in safe_answer: {e}",
            extra={"user_id": message.from_user.id if message.from_user else None},
        )
        raise


async def safe_edit_text(
    message: Message,
    text: str,
    parse_mode: str | None = "Markdown",
    reply_markup: InlineKeyboardMarkup | None = None,
    **kwargs: Any,
) -> Message | bool | None:
    """
    Safely edit a message with automatic Markdown error recovery.

    Args:
        message: Message to edit
        text: New message text
        parse_mode: Parse mode
        reply_markup: Optional inline keyboard
        **kwargs: Additional arguments

    Returns:
        Edited message, True, or None if failed
    """
    try:
        return await message.edit_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs,
        )
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e):
            logger.warning(
                f"Markdown parsing failed in edit_text, retrying: {e}",
                extra={
                    "chat_id": message.chat.id,
                    "message_id": message.message_id,
                },
            )
            try:
                return await message.edit_text(
                    text,
                    parse_mode=None,
                    reply_markup=reply_markup,
                    **kwargs,
                )
            except Exception as retry_error:
                logger.error(f"Failed to edit message: {retry_error}")
                return None
        elif "message is not modified" in str(e):
            # Not an error - message content is the same
            return True
        else:
            raise
    except Exception as e:
        logger.error(f"Unexpected error in safe_edit_text: {e}")
        raise


async def safe_send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    parse_mode: str | None = "Markdown",
    reply_markup: InlineKeyboardMarkup
    | ReplyKeyboardMarkup
    | ReplyKeyboardRemove
    | ForceReply
    | None = None,
    **kwargs: Any,
) -> Message | None:
    """
    Safely send a message to a specific chat with error recovery.

    Args:
        bot: Bot instance
        chat_id: Target chat ID
        text: Message text
        parse_mode: Parse mode
        reply_markup: Optional keyboard
        **kwargs: Additional arguments

    Returns:
        Sent message or None if failed
    """
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs,
        )
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e):
            logger.warning(
                f"Markdown parsing failed in send_message, retrying: {e}",
                extra={"chat_id": chat_id, "text_length": len(text)},
            )
            try:
                return await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=None,
                    reply_markup=reply_markup,
                    **kwargs,
                )
            except Exception as retry_error:
                logger.error(f"Failed to send message to {chat_id}: {retry_error}")
                return None
        elif "chat not found" in str(e).lower() or "blocked" in str(e).lower():
            logger.warning(f"Cannot send to chat {chat_id}: {e}")
            return None
        else:
            raise
    except Exception as e:
        logger.error(f"Unexpected error in safe_send_message: {e}")
        raise


def build_safe_text(
    template: str,
    **kwargs: Any,
) -> str:
    """
    Build message text with automatic escaping of dynamic values.

    Values that should be escaped are prefixed with 'safe_' in kwargs.
    Regular values are inserted as-is.

    Example:
        build_safe_text(
            "Hello, {username}! Your code: {code}",
            safe_username="user_name",  # Will be escaped
            code="`ABC123`",  # Will NOT be escaped (already formatted)
        )

    Args:
        template: Message template with {placeholder} syntax
        **kwargs: Values to substitute. Prefix with 'safe_' for auto-escaping.

    Returns:
        Formatted text with escaped values
    """
    # Process safe_ prefixed values
    processed_kwargs = {}
    for key, value in kwargs.items():
        if key.startswith("safe_"):
            actual_key = key[5:]  # Remove 'safe_' prefix
            processed_kwargs[actual_key] = escape_md(str(value) if value else "")
        else:
            processed_kwargs[key] = value

    return template.format(**processed_kwargs)
