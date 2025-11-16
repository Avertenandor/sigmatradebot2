"""
Notification utilities.

Helper functions for sending notifications.
"""

from aiogram import Bot
from loguru import logger


async def notify_admins(
    bot: Bot,
    admin_ids: list[int],
    message: str,
    parse_mode: str = "Markdown",
) -> None:
    """
    Send notification to all admins.

    Args:
        bot: Bot instance
        admin_ids: List of admin Telegram IDs
        message: Message to send
        parse_mode: Parse mode (Markdown, HTML)
    """
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                admin_id,
                message,
                parse_mode=parse_mode,
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
