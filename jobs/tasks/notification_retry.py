"""
Notification retry task (PART5 critical).

Processes failed notification retries with exponential backoff.
Runs every minute to check for notifications ready for retry.
"""

import asyncio

import dramatiq
from aiogram import Bot
from loguru import logger

from app.config.database import async_session_maker
from app.config.settings import settings
from app.services.notification_retry_service import (
    NotificationRetryService,
)


@dramatiq.actor(max_retries=3, time_limit=300_000)  # 5 min timeout
def process_notification_retries() -> dict:
    """
    Process failed notification retries.

    PART5 critical: Ensures failed notifications are retried with
    exponential backoff (1min, 5min, 15min, 1h, 2h) up to 5 attempts.

    Returns:
        Dict with processed, successful, failed, gave_up counts
    """
    logger.info("Starting notification retry processing...")

    try:
        # Run async code
        result = asyncio.run(_process_notification_retries_async())

        logger.info(
            f"Notification retry processing complete: "
            f"{result['successful']} successful, "
            f"{result['failed']} failed, "
            f"{result['gave_up']} gave up"
        )

        return result

    except Exception as e:
        logger.exception(f"Notification retry processing failed: {e}")
        return {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "gave_up": 0,
            "error": str(e),
        }


async def _process_notification_retries_async() -> dict:
    """Async implementation of notification retry processing."""
    async with async_session_maker() as session:
        # Initialize bot
        bot = Bot(token=settings.telegram_bot_token)

        try:
            # Process retries
            retry_service = NotificationRetryService(session, bot)
            result = await retry_service.process_pending_retries()

            return result
        finally:
            await bot.session.close()
