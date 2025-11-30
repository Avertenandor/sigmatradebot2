"""
Log aggregation service.

R14-3: Aggregates and analyzes logs for error patterns and frequency.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from aiogram import Bot

# Error frequency thresholds
ERROR_FREQUENCY_WARNING = 10  # errors per minute
ERROR_FREQUENCY_CRITICAL = 50  # errors per minute
USER_ERROR_THRESHOLD = 20  # errors per user per hour


class LogAggregationService:
    """
    R14-3: Log aggregation and error analysis service.

    Groups errors by type, counts frequency, and alerts on thresholds.
    """

    def __init__(
        self, session: AsyncSession, bot: "Bot | None" = None
    ) -> None:
        """
        Initialize log aggregation service.

        Args:
            session: Database session
            bot: Optional Bot instance for sending admin notifications
        """
        self.session = session
        self.bot = bot
        # In-memory error tracking (in production, use Redis or database)
        self._error_counts: dict[str, list[datetime]] = defaultdict(list)
        self._user_error_counts: dict[int, list[datetime]] = defaultdict(list)

    async def record_error(
        self,
        error_type: str,
        error_message: str,
        user_id: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Record error for aggregation.

        R14-3: Called when an error occurs to track patterns.

        Args:
            error_type: Type of error (e.g., "DatabaseError", "BlockchainError")
            error_message: Error message
            user_id: Optional user ID
            context: Optional context data
        """
        now = datetime.now(UTC)

        # Create error fingerprint
        error_fingerprint = f"{error_type}:{error_message[:100]}"

        # Record error
        self._error_counts[error_fingerprint].append(now)

        # Record user-specific error
        if user_id:
            self._user_error_counts[user_id].append(now)

        # Clean old entries (older than 1 hour)
        cutoff = now - timedelta(hours=1)
        self._error_counts[error_fingerprint] = [
            ts
            for ts in self._error_counts[error_fingerprint]
            if ts > cutoff
        ]

        if user_id:
            self._user_error_counts[user_id] = [
                ts
                for ts in self._user_error_counts[user_id]
                if ts > cutoff
            ]

        # Check thresholds and alert
        await self._check_thresholds(error_fingerprint, user_id)

    async def _check_thresholds(
        self, error_fingerprint: str, user_id: int | None
    ) -> None:
        """
        Check error frequency thresholds and alert if exceeded.

        Args:
            error_fingerprint: Error fingerprint
            user_id: Optional user ID
        """
        now = datetime.now(UTC)

        # Check error frequency (last minute)
        minute_ago = now - timedelta(minutes=1)
        recent_errors = [
            ts
            for ts in self._error_counts[error_fingerprint]
            if ts > minute_ago
        ]
        error_count = len(recent_errors)

        if error_count >= ERROR_FREQUENCY_CRITICAL:
            logger.critical(
                "R14-3: CRITICAL error frequency detected",
                extra={
                    "error_fingerprint": error_fingerprint,
                    "count": error_count,
                    "threshold": ERROR_FREQUENCY_CRITICAL,
                    "time_window": "1 minute",
                },
            )
            # Send alert to admins via Telegram
            await self._send_critical_alert(error_fingerprint, error_count)

        elif error_count >= ERROR_FREQUENCY_WARNING:
            logger.warning(
                "R14-3: High error frequency detected",
                extra={
                    "error_fingerprint": error_fingerprint,
                    "count": error_count,
                    "threshold": ERROR_FREQUENCY_WARNING,
                    "time_window": "1 minute",
                },
            )

        # Check user-specific error threshold
        if user_id:
            hour_ago = now - timedelta(hours=1)
            user_recent_errors = [
                ts
                for ts in self._user_error_counts[user_id]
                if ts > hour_ago
            ]
            user_error_count = len(user_recent_errors)

            if user_error_count >= USER_ERROR_THRESHOLD:
                logger.warning(
                    "R14-3: User error threshold exceeded",
                    extra={
                        "user_id": user_id,
                        "error_count": user_error_count,
                        "threshold": USER_ERROR_THRESHOLD,
                        "time_window": "1 hour",
                        "potential_abuse": True,
                    },
                )

    async def _send_critical_alert(
        self, error_fingerprint: str, count: int
    ) -> None:
        """
        Send critical alert to admins.

        R14-3: Integrates with NotificationService to send alerts to super_admins.

        Args:
            error_fingerprint: Error fingerprint
            count: Error count
        """
        logger.critical(
            "R14-3: CRITICAL ALERT - Error frequency exceeded",
            extra={
                "error_fingerprint": error_fingerprint,
                "count": count,
                "action_required": "immediate_investigation",
            },
        )

        # R14-3: Send notification to admins if bot is available
        if self.bot:
            try:
                from app.repositories.admin_repository import AdminRepository
                from app.services.notification_service import (
                    NotificationService,
                )

                notification_service = NotificationService(self.session)
                admin_repo = AdminRepository(self.session)

                # Get all super_admins
                all_admins = await admin_repo.find_by()
                super_admins = [
                    a for a in all_admins
                    if hasattr(a, "is_super_admin") and a.is_super_admin
                ]

                if super_admins:
                    # Build notification message
                    message = (
                        f"🚨 **CRITICAL: High Error Frequency Detected**\n\n"
                        f"**Error:** `{error_fingerprint[:200]}`\n"
                        f"**Count:** {count} errors per minute\n"
                        f"**Threshold:** {ERROR_FREQUENCY_CRITICAL} errors/min\n\n"
                        f"**Action Required:** Immediate investigation"
                    )

                    # Send to all super_admins
                    notified_count = await notification_service.notify_admins(
                        self.bot, message, critical=True
                    )

                    logger.info(
                        f"R14-3: Critical alert sent to {notified_count} super_admins"
                    )
                else:
                    logger.warning(
                        "R14-3: No super_admins found to notify about critical error"
                    )
            except Exception as e:
                # Don't fail if notification fails
                logger.error(
                    f"R14-3: Failed to send critical alert to admins: {e}",
                    exc_info=True,
                )
        else:
            logger.warning(
                "R14-3: Bot instance not provided, cannot send admin notifications. "
                "Critical alert logged only."
            )

    async def get_error_statistics(
        self, time_window_minutes: int = 60
    ) -> dict[str, Any]:
        """
        Get error statistics for time window.

        R14-3: Returns aggregated error data.

        Args:
            time_window_minutes: Time window in minutes

        Returns:
            Dict with error statistics
        """
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=time_window_minutes)

        # Group errors by fingerprint
        error_groups: dict[str, int] = {}
        for fingerprint, timestamps in self._error_counts.items():
            recent = [ts for ts in timestamps if ts > cutoff]
            if recent:
                error_groups[fingerprint] = len(recent)

        # Sort by frequency
        sorted_errors = sorted(
            error_groups.items(), key=lambda x: x[1], reverse=True
        )

        return {
            "time_window_minutes": time_window_minutes,
            "total_errors": sum(error_groups.values()),
            "unique_errors": len(error_groups),
            "top_errors": sorted_errors[:10],  # Top 10
            "timestamp": now.isoformat(),
        }

    async def get_user_error_statistics(
        self, user_id: int, time_window_hours: int = 24
    ) -> dict[str, Any]:
        """
        Get error statistics for specific user.

        Args:
            user_id: User ID
            time_window_hours: Time window in hours

        Returns:
            Dict with user error statistics
        """
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=time_window_hours)

        user_errors = [
            ts
            for ts in self._user_error_counts.get(user_id, [])
            if ts > cutoff
        ]

        return {
            "user_id": user_id,
            "time_window_hours": time_window_hours,
            "error_count": len(user_errors),
            "potential_abuse": len(user_errors) >= USER_ERROR_THRESHOLD,
            "timestamp": now.isoformat(),
        }
