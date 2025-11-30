"""
Admin Security Monitor.

R10-3: Monitors admin actions for suspicious patterns and automatically
blocks compromised admins.

Detects:
- Mass bans/terminations (>20/hour)
- Mass withdrawal approvals (>50/hour)
- Admin creation/deletion spikes (>5/day)
- Unusual timing (3am operations)
- Large withdrawal approvals (>$1000)
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.admin_action import AdminAction
from app.repositories.admin_action_repository import AdminActionRepository
from app.repositories.admin_repository import AdminRepository


class AdminSecurityMonitor:
    """
    R10-3: Monitor admin actions for compromise detection.

    Automatically blocks admins when suspicious patterns are detected.
    Thresholds are configurable via settings.py / .env
    """

    def __init__(
        self,
        session: AsyncSession,
        bot: Any | None = None,
        redis_client: Any | None = None,
    ) -> None:
        """
        Initialize admin security monitor.

        Args:
            session: Database session
            bot: Optional Bot instance for notifications
            redis_client: Optional Redis client for temporary blocks
        """
        self.session = session
        self.bot = bot
        self.redis_client = redis_client
        self.action_repo = AdminActionRepository(session)
        self.admin_repo = AdminRepository(session)

    async def check_action(
        self,
        admin_id: int,
        action_type: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Check if admin action is suspicious.

        R10-3: Called after each admin action to detect compromise.

        Args:
            admin_id: Admin who performed action
            action_type: Type of action
            details: Action details (for withdrawal amounts, etc.)

        Returns:
            Dict with:
                - suspicious: bool
                - reason: str | None
                - should_block: bool
                - severity: "critical" | "high" | "medium"
        """
        try:
            # Get admin
            admin = await self.admin_repo.get_by_id(admin_id)
            if not admin:
                return {
                    "suspicious": False,
                    "reason": None,
                    "should_block": False,
                    "severity": None,
                }

            # Check different action types
            if action_type in ("USER_BLOCKED", "USER_TERMINATED"):
                return await self._check_mass_user_actions(
                    admin_id, action_type
                )
            elif action_type == "WITHDRAWAL_APPROVED":
                return await self._check_withdrawal_approval(
                    admin_id, details
                )
            elif action_type == "BALANCE_ADJUSTMENT":
                # R18-4: Check balance adjustment limits
                return await self._check_balance_adjustment_limits(admin_id)
            elif action_type in ("ADMIN_CREATED", "ADMIN_DELETED"):
                return await self._check_admin_management(admin_id, action_type)
            elif action_type in (
                "SETTINGS_CHANGED",
                "WALLET_CHANGED",
                "SYSTEM_CONFIG_CHANGED",
            ):
                return await self._check_critical_config_changes(
                    admin_id, action_type
                )

            # No suspicious pattern detected
            return {
                "suspicious": False,
                "reason": None,
                "should_block": False,
                "severity": None,
            }

        except Exception as e:
            logger.error(
                f"Error checking admin action: {e}",
                extra={"admin_id": admin_id, "action_type": action_type},
            )
            # On error, don't block (fail open)
            return {
                "suspicious": False,
                "reason": None,
                "should_block": False,
                "severity": None,
            }

    async def _check_mass_user_actions(
        self, admin_id: int, action_type: str
    ) -> dict[str, Any]:
        """Check for mass bans/terminations."""
        threshold = (
            settings.admin_max_bans_per_hour
            if action_type == "USER_BLOCKED"
            else settings.admin_max_terminations_per_hour
        )

        # Count actions in last hour
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        count = await self.action_repo.count_by_admin_and_type(
            admin_id=admin_id,
            action_type=action_type,
            since=one_hour_ago,
        )

        if count >= threshold:
            severity = "critical" if count >= threshold * 2 else "high"
            return {
                "suspicious": True,
                "reason": (
                    f"Mass {action_type.lower()}: {count} actions in last hour "
                    f"(threshold: {threshold})"
                ),
                "should_block": True,
                "severity": severity,
            }

        return {
            "suspicious": False,
            "reason": None,
            "should_block": False,
            "severity": None,
        }

    async def _check_withdrawal_approval(
        self, admin_id: int, details: dict[str, Any] | None
    ) -> dict[str, Any]:
        """
        Check for mass or large withdrawal approvals.

        R18-4: Also checks daily limits (count and total amount).
        """
        # Count approvals in last hour
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        count = await self.action_repo.count_by_admin_and_type(
            admin_id=admin_id,
            action_type="WITHDRAWAL_APPROVED",
            since=one_hour_ago,
        )

        # Check for mass approvals (hourly)
        if count >= settings.admin_max_withdrawal_approvals_per_hour:
            return {
                "suspicious": True,
                "reason": (
                    f"Mass withdrawal approvals: {count} in last hour "
                    f"(threshold: {settings.admin_max_withdrawal_approvals_per_hour})"
                ),
                "should_block": True,
                "severity": "critical",
            }

        # R18-4: Check daily limits
        one_day_ago = datetime.now(UTC) - timedelta(days=1)
        daily_count = await self.action_repo.count_by_admin_and_type(
            admin_id=admin_id,
            action_type="WITHDRAWAL_APPROVED",
            since=one_day_ago,
        )

        if daily_count >= settings.admin_max_withdrawals_per_day:
            return {
                "suspicious": True,
                "reason": (
                    f"Daily withdrawal limit exceeded: {daily_count} withdrawals "
                    f"(threshold: {settings.admin_max_withdrawals_per_day}/day)"
                ),
                "should_block": True,
                "severity": "critical",
            }

        # R18-4: Check daily total amount limit
        daily_total = await self.action_repo.sum_withdrawal_amounts_by_admin(
            admin_id, one_day_ago
        )

        if daily_total >= settings.admin_max_withdrawal_amount_per_day:
            return {
                "suspicious": True,
                "reason": (
                    f"Daily withdrawal amount limit exceeded: "
                    f"${daily_total:.2f} USDT "
                    f"(threshold: ${settings.admin_max_withdrawal_amount_per_day}/day)"
                ),
                "should_block": True,
                "severity": "critical",
            }

        # Check for large withdrawal (>$1000)
        if details:
            amount = details.get("amount")
            if amount:
                try:
                    amount_decimal = Decimal(str(amount))
                    if amount_decimal >= settings.admin_large_withdrawal_threshold:
                        # Count large withdrawals in last hour
                        large_count = await self._count_large_withdrawals(
                            admin_id, one_hour_ago
                        )
                        max_large = settings.admin_max_large_withdrawal_approvals_per_hour
                        if large_count >= max_large:
                            return {
                                "suspicious": True,
                                "reason": (
                                    f"Mass large withdrawal approvals: "
                                    f"{large_count} >${settings.admin_large_withdrawal_threshold} "
                                    f"in last hour"
                                ),
                                "should_block": True,
                                "severity": "critical",
                            }
                except (ValueError, TypeError):
                    pass

        return {
            "suspicious": False,
            "reason": None,
            "should_block": False,
            "severity": None,
        }

    async def _check_admin_management(
        self, admin_id: int, action_type: str
    ) -> dict[str, Any]:
        """Check for admin creation/deletion spikes."""
        threshold = (
            settings.admin_max_creations_per_day
            if action_type == "ADMIN_CREATED"
            else settings.admin_max_deletions_per_day
        )

        # Count actions in last 24 hours
        one_day_ago = datetime.now(UTC) - timedelta(days=1)
        count = await self.action_repo.count_by_admin_and_type(
            admin_id=admin_id,
            action_type=action_type,
            since=one_day_ago,
        )

        if count >= threshold:
            return {
                "suspicious": True,
                "reason": (
                    f"Mass {action_type.lower()}: {count} in last 24 hours "
                    f"(threshold: {threshold})"
                ),
                "should_block": True,
                "severity": "critical",
            }

        return {
            "suspicious": False,
            "reason": None,
            "should_block": False,
            "severity": None,
        }

    async def _check_critical_config_changes(
        self, admin_id: int, action_type: str
    ) -> dict[str, Any]:
        """Check for critical configuration changes."""
        # Any critical config change is suspicious if done outside business hours
        # (3am-6am UTC is suspicious)
        now = datetime.now(UTC)
        hour = now.hour

        if 3 <= hour < 6:
            return {
                "suspicious": True,
                "reason": (
                    f"Critical config change ({action_type}) "
                    f"at unusual time ({hour}:00 UTC)"
                ),
                "should_block": False,  # Don't auto-block, but alert
                "severity": "high",
            }

        return {
            "suspicious": False,
            "reason": None,
            "should_block": False,
            "severity": None,
        }

    async def _count_large_withdrawals(
        self, admin_id: int, since: datetime
    ) -> int:
        """Count large withdrawal approvals by admin since timestamp."""
        stmt = (
            select(func.count(AdminAction.id))
            .where(AdminAction.admin_id == admin_id)
            .where(AdminAction.action_type == "WITHDRAWAL_APPROVED")
            .where(AdminAction.created_at >= since)
        )

        result = await self.session.execute(stmt)
        count = result.scalar() or 0

        # Filter by amount in details (if available)
        # This is simplified - in production, would need to parse JSON details
        return count

    async def block_admin(
        self, admin_id: int, reason: str
    ) -> tuple[bool, str | None]:
        """
        Block compromised admin.

        R10-3: Automatically blocks admin when compromise detected.

        Args:
            admin_id: Admin to block
            reason: Block reason

        Returns:
            Tuple of (success, error_message)
        """
        try:
            admin = await self.admin_repo.get_by_id(admin_id)
            if not admin:
                return False, "Admin not found"

            # R10-3: Mark admin as blocked
            logger.critical(
                f"R10-3: Admin {admin_id} being blocked: {reason}",
                extra={
                    "admin_id": admin_id,
                    "admin_telegram_id": admin.telegram_id,
                    "reason": reason,
                },
            )

            # Update is_blocked field
            await self.admin_repo.update(admin_id, is_blocked=True)

            # Invalidate all sessions for this admin
            await self._force_logout(admin_id)

            # Block critical operations
            await self._block_critical_operations(admin_id)

            # Notify super_admins
            await self._notify_super_admins(
                admin_id, reason, severity="critical"
            )

            await self.session.commit()

            return True, None

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to block admin {admin_id}: {e}")
            return False, str(e)

    async def _notify_super_admins(
        self, admin_id: int, reason: str, severity: str = "high"
    ) -> None:
        """
        Notify super_admins about suspicious admin activity.

        R10-3: Sends Telegram notifications to all super_admins.

        Args:
            admin_id: Admin ID with suspicious activity
            reason: Reason for notification
            severity: Severity level ("critical" | "high" | "medium")
        """
        if not self.bot:
            logger.warning(
                "Bot instance not provided, cannot send super_admin notifications"
            )
            return

        try:
            from app.services.notification_service import NotificationService

            # Get admin details
            admin = await self.admin_repo.get_by_id(admin_id)
            if not admin:
                return

            # Get all super_admins
            all_admins = await self.admin_repo.find_by()
            super_admins = [a for a in all_admins if a.is_super_admin]

            if not super_admins:
                logger.warning("No super_admins found to notify")
                return

            # Build notification message
            emoji = "🚨" if severity == "critical" else "⚠️"
            message = (
                f"{emoji} **SECURITY ALERT: Suspicious Admin Activity**\n\n"
                f"**Admin:** {admin.display_name or admin.telegram_id}\n"
                f"**Admin ID:** {admin_id}\n"
                f"**Severity:** {severity.upper()}\n"
                f"**Reason:** {reason}\n\n"
                f"Action required: Review admin activity immediately."
            )

            # Send notifications
            notification_service = NotificationService(self.session)
            for super_admin in super_admins:
                try:
                    await notification_service.send_notification(
                        bot=self.bot,
                        user_telegram_id=super_admin.telegram_id,
                        message=message,
                        critical=(severity == "critical"),
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to notify super_admin {super_admin.id}: {e}"
                    )

        except Exception as e:
            logger.error(f"Error notifying super_admins: {e}", exc_info=True)

    async def _force_logout(self, admin_id: int) -> None:
        """
        Force logout admin by invalidating all sessions.

        R10-3: Deactivates all active admin sessions.

        Args:
            admin_id: Admin ID to logout
        """
        try:
            from app.repositories.admin_session_repository import (
                AdminSessionRepository,
            )

            session_repo = AdminSessionRepository(self.session)
            deactivated_count = await session_repo.deactivate_all_sessions(admin_id)
            await self.session.commit()

            logger.warning(
                f"R10-3: Forced logout for admin {admin_id}: "
                f"{deactivated_count} sessions deactivated"
            )

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error forcing logout for admin {admin_id}: {e}")

    async def _block_critical_operations(self, admin_id: int) -> None:
        """
        Temporarily block critical operations for compromised admin.

        R10-3: Sets Redis flag to block critical operations.
        R11-2: Gracefully handles Redis failures.

        Args:
            admin_id: Admin ID to block
        """
        if not self.redis_client:
            logger.warning(
                "R11-2: Redis client not provided, cannot set operation block. "
                "Admin will be blocked via database flag only."
            )
            return

        try:
            # Block for 1 hour (3600 seconds)
            block_key = f"admin:{admin_id}:operations_blocked"
            await self.redis_client.set(block_key, "1", ex=3600)

            logger.warning(
                f"R10-3: Critical operations blocked for admin {admin_id} "
                f"for 1 hour"
            )
        except Exception as e:
            # R11-2: Redis failed, but admin is already blocked in database
            logger.warning(
                f"R11-2: Failed to set Redis block for admin {admin_id}: {e}. "
                "Admin is still blocked via database flag."
            )
            logger.error(
                f"Error blocking operations for admin {admin_id}: {e}"
            )
