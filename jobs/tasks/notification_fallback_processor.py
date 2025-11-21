"""
Notification fallback processor task.

R11-3: Processes notifications from PostgreSQL fallback queue when Redis is unavailable.
Polls the notification_queue_fallback table every 5 seconds and sends pending notifications.
"""

import asyncio
from datetime import UTC, datetime

import dramatiq
from aiogram import Bot
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import async_session_maker
from app.config.settings import settings
from app.models.notification_queue_fallback import NotificationQueueFallback
from app.services.notification_service import NotificationService


@dramatiq.actor(max_retries=3, time_limit=300_000)  # 5 min timeout
def process_notification_fallback() -> dict:
    """
    Process notifications from PostgreSQL fallback queue.

    R11-3: Polls notification_queue_fallback table and sends pending notifications.

    Returns:
        Dict with processed, sent, failed counts
    """
    logger.info("R11-3: Starting notification fallback processing...")

    try:
        result = asyncio.run(_process_notification_fallback_async())
        logger.info(
            f"R11-3: Notification fallback processing complete: "
            f"{result['sent']} sent, {result['failed']} failed"
        )
        return result
    except Exception as e:
        logger.exception(f"R11-3: Notification fallback processing failed: {e}")
        return {
            "processed": 0,
            "sent": 0,
            "failed": 0,
            "error": str(e),
        }


async def _process_notification_fallback_async() -> dict:
    """Async implementation of notification fallback processing."""
    async with async_session_maker() as session:
        # Get pending notifications (processed_at is NULL)
        stmt = (
            select(NotificationQueueFallback)
            .where(NotificationQueueFallback.processed_at.is_(None))
            .order_by(
                NotificationQueueFallback.priority.desc(),  # Higher priority first
                NotificationQueueFallback.created_at.asc(),  # Older first
            )
            .limit(100)  # Process up to 100 notifications per run
        )

        result = await session.execute(stmt)
        pending_notifications = list(result.scalars().all())

        if not pending_notifications:
            logger.debug("R11-3: No pending notifications in fallback queue")
            return {
                "processed": 0,
                "sent": 0,
                "failed": 0,
            }

        logger.info(
            f"R11-3: Processing {len(pending_notifications)} pending notifications"
        )

        bot = Bot(token=settings.telegram_bot_token)
        notification_service = NotificationService(session)

        sent = 0
        failed = 0

        for notification in pending_notifications:
            try:
                # Extract payload
                payload = notification.payload
                message = payload.get("message", "")
                critical = payload.get("critical", False)

                if not message:
                    logger.warning(
                        f"R11-3: Notification {notification.id} has empty message"
                    )
                    # Mark as processed to avoid reprocessing
                    notification.processed_at = datetime.now(UTC)
                    failed += 1
                    continue

                # Get user telegram_id
                user = notification.user
                if not user:
                    logger.warning(
                        f"R11-3: Notification {notification.id} has no user"
                    )
                    notification.processed_at = datetime.now(UTC)
                    failed += 1
                    continue

                # Send notification (without Redis to avoid recursion)
                success = await notification_service.send_notification(
                    bot=bot,
                    user_telegram_id=user.telegram_id,
                    message=message,
                    critical=critical,
                    redis_client=None,  # Don't use Redis to avoid recursion
                )

                if success:
                    # Mark as processed
                    notification.processed_at = datetime.now(UTC)
                    sent += 1
                    logger.info(
                        f"R11-3: Notification {notification.id} sent successfully "
                        f"to user {user.telegram_id}"
                    )
                else:
                    # Keep as pending for retry
                    failed += 1
                    logger.warning(
                        f"R11-3: Failed to send notification {notification.id} "
                        f"to user {user.telegram_id}"
                    )

            except Exception as e:
                logger.error(
                    f"R11-3: Error processing notification {notification.id}: {e}",
                    extra={"notification_id": notification.id},
                    exc_info=True,
                )
                failed += 1

        await session.commit()
        await bot.session.close()

        return {
            "processed": len(pending_notifications),
            "sent": sent,
            "failed": failed,
        }

