"""
Notification retry service (PART5 critical).

Handles retrying failed notification deliveries with exponential backoff.
Ensures users don't miss critical notifications.
"""

from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.failed_notification import FailedNotification
from app.repositories.failed_notification_repository import (
    FailedNotificationRepository,
)


# Retry configuration: 1min, 5min, 15min, 1h, 2h
RETRY_DELAYS_MINUTES = [1, 5, 15, 60, 120]
MAX_RETRIES = 5


class NotificationRetryService:
    """Notification retry service with exponential backoff."""

    def __init__(
        self, session: AsyncSession, bot: Bot
    ) -> None:
        """Initialize notification retry service."""
        self.session = session
        self.bot = bot
        self.failed_repo = FailedNotificationRepository(session)

    async def process_pending_retries(self) -> dict:
        """
        Process pending failed notifications.

        Called by background job.

        Returns:
            Dict with processed, successful, failed, gave_up counts
        """
        # Get failed notifications ready for retry
        now = datetime.utcnow()

        # Get pending notifications (not resolved, under max retries)
        pending = await self.failed_repo.get_pending_for_retry(
            max_attempts=MAX_RETRIES, limit=100
        )

        if not pending:
            logger.debug("No failed notifications to retry")
            return {
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "gave_up": 0,
            }

        logger.info(
            f"Processing {len(pending)} failed notifications..."
        )

        successful = 0
        failed = 0
        gave_up = 0

        for notification in pending:
            try:
                # Check if enough time has passed since last attempt
                if notification.last_attempt_at:
                    time_since_last = (
                        now - notification.last_attempt_at
                    ).total_seconds() / 60  # Convert to minutes

                    # Get required delay based on attempt count
                    attempt_idx = min(
                        notification.attempt_count,
                        len(RETRY_DELAYS_MINUTES) - 1,
                    )
                    required_delay = RETRY_DELAYS_MINUTES[attempt_idx]

                    if time_since_last < required_delay:
                        logger.debug(
                            "Notification not ready for retry yet",
                            extra={
                                "id": notification.id,
                                "attempt_count": notification.attempt_count,
                                "time_since_last_minutes": time_since_last,
                                "required_delay_minutes": required_delay,
                            },
                        )
                        continue

                # Attempt to send notification
                try:
                    await self.bot.send_message(
                        chat_id=notification.user_telegram_id,
                        text=notification.message,
                        parse_mode="Markdown",
                    )

                    # Success - mark as resolved
                    await self.failed_repo.update(
                        notification.id,
                        resolved=True,
                        resolved_at=datetime.utcnow(),
                    )

                    successful += 1

                    logger.info(
                        "Notification retry successful",
                        extra={
                            "id": notification.id,
                            "telegram_id": notification.user_telegram_id,
                            "type": notification.notification_type,
                            "attempt_count": notification.attempt_count,
                        },
                    )

                except Exception as send_error:
                    # Failed - increment counter
                    error_msg = str(send_error)

                    await self.failed_repo.update(
                        notification.id,
                        attempt_count=notification.attempt_count + 1,
                        last_error=error_msg,
                        last_attempt_at=datetime.utcnow(),
                    )

                    failed += 1

                    logger.warning(
                        "Notification retry failed",
                        extra={
                            "id": notification.id,
                            "telegram_id": notification.user_telegram_id,
                            "type": notification.notification_type,
                            "attempt_count": notification.attempt_count + 1,
                            "error": error_msg,
                        },
                    )

                    # If max retries reached, give up
                    if notification.attempt_count + 1 >= MAX_RETRIES:
                        gave_up += 1

                        logger.error(
                            "Notification gave up after max retries",
                            extra={
                                "id": notification.id,
                                "telegram_id": notification.user_telegram_id,
                                "type": notification.notification_type,
                                "attempt_count": notification.attempt_count + 1,
                            },
                        )

            except Exception as e:
                logger.error(
                    f"Error processing notification retry "
                    f"{notification.id}: {e}"
                )
                failed += 1

        await self.session.commit()

        logger.info(
            "Notification retry batch complete",
            extra={
                "processed": len(pending),
                "successful": successful,
                "failed": failed,
                "gave_up": gave_up,
            },
        )

        return {
            "processed": len(pending),
            "successful": successful,
            "failed": failed,
            "gave_up": gave_up,
        }

    async def get_statistics(self) -> dict:
        """
        Get statistics about failed notifications.

        Returns:
            Dict with comprehensive notification stats
        """
        # Get counts
        all_failed = await self.failed_repo.find_all()
        total = len(all_failed)

        unresolved = len(
            await self.failed_repo.find_by(resolved=False)
        )

        critical = len(
            await self.failed_repo.get_critical_unresolved()
        )

        # Get counts by type
        by_type = {}
        unresolved_notifications = await self.failed_repo.find_by(
            resolved=False
        )

        for notification in unresolved_notifications:
            ntype = notification.notification_type
            by_type[ntype] = by_type.get(ntype, 0) + 1

        return {
            "total": total,
            "unresolved": unresolved,
            "critical": critical,
            "by_type": by_type,
        }

    async def resolve_notification(
        self, notification_id: int
    ) -> bool:
        """
        Manually resolve failed notification (admin action).

        Args:
            notification_id: Notification ID

        Returns:
            Success flag
        """
        notification = await self.failed_repo.get_by_id(
            notification_id
        )

        if not notification:
            logger.warning(
                "Notification not found for manual resolution",
                extra={"notification_id": notification_id},
            )
            return False

        await self.failed_repo.update(
            notification_id,
            resolved=True,
            resolved_at=datetime.utcnow(),
        )

        await self.session.commit()

        logger.info(
            "Notification manually resolved",
            extra={
                "id": notification_id,
                "telegram_id": notification.user_telegram_id,
                "type": notification.notification_type,
            },
        )

        return True
