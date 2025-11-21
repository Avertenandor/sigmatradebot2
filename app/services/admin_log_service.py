"""
Admin log service.

Handles logging of admin actions for audit trail.
"""

from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.repositories.admin_action_repository import AdminActionRepository


class AdminLogService:
    """Service for logging admin actions."""

    def __init__(
        self,
        session: AsyncSession,
        bot: Any | None = None,
        redis_client: Any | None = None,
    ) -> None:
        """
        Initialize admin log service.

        Args:
            session: Database session
            bot: Optional Bot instance for security notifications
            redis_client: Optional Redis client for operation blocks
        """
        self.session = session
        self.bot = bot
        self.redis_client = redis_client
        self.action_repo = AdminActionRepository(session)

    async def log_action(
        self,
        admin_id: int,
        action_type: str,
        target_user_id: int | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        """
        Log admin action.

        Args:
            admin_id: Admin who performed action
            action_type: Type of action
            target_user_id: Target user ID (optional)
            details: Additional details (JSON)
            ip_address: IP address (optional)
        """
        try:
            await self.action_repo.create(
                admin_id=admin_id,
                action_type=action_type,
                target_user_id=target_user_id,
                details=details,
                ip_address=ip_address,
            )
            await self.session.commit()

            logger.debug(
                f"Admin action logged: {action_type} by admin {admin_id}"
            )

            # R10-3: Check for suspicious activity after logging
            try:
                from app.services.admin_security_monitor import (
                    AdminSecurityMonitor,
                )

                monitor = AdminSecurityMonitor(
                    self.session, bot=self.bot, redis_client=self.redis_client
                )
                check_result = await monitor.check_action(
                    admin_id=admin_id,
                    action_type=action_type,
                    details=details,
                )

                if check_result.get("suspicious"):
                    logger.warning(
                        f"R10-3: Suspicious admin activity detected",
                        extra={
                            "admin_id": admin_id,
                            "action_type": action_type,
                            "reason": check_result.get("reason"),
                            "severity": check_result.get("severity"),
                        },
                    )

                    # Auto-block if should_block is True
                    if check_result.get("should_block"):
                        # R10-3: Notify super_admins, force logout, block operations
                        await monitor._notify_super_admins(
                            admin_id=admin_id,
                            reason=check_result.get("reason", "Suspicious activity"),
                            severity=check_result.get("severity", "critical"),
                        )
                        await monitor._force_logout(admin_id)
                        await monitor._block_critical_operations(admin_id)

                        success, error = await monitor.block_admin(
                            admin_id, check_result.get("reason", "Suspicious activity")
                        )
                        if success:
                            logger.critical(
                                f"R10-3: Admin {admin_id} automatically blocked "
                                f"due to suspicious activity"
                            )
                        else:
                            logger.error(
                                f"R10-3: Failed to auto-block admin {admin_id}: {error}"
                            )
                    elif check_result.get("severity") in ("critical", "high"):
                        # Notify even if not blocking
                        await monitor._notify_super_admins(
                            admin_id=admin_id,
                            reason=check_result.get("reason", "Suspicious activity"),
                            severity=check_result.get("severity", "high"),
                        )

            except Exception as monitor_error:
                # Don't fail the action if monitoring fails
                logger.error(
                    f"Error in admin security monitor: {monitor_error}",
                    exc_info=True,
                )

        except Exception as e:
            logger.error(
                f"Failed to log admin action: {e}",
                extra={
                    "admin_id": admin_id,
                    "action_type": action_type,
                },
            )
            # Don't raise - logging failure shouldn't break the action

    async def log_admin_created(
        self,
        admin: Admin,
        created_admin_id: int,
        created_admin_telegram_id: int,
        role: str,
    ) -> None:
        """
        Log admin creation.

        Args:
            admin: Admin who created the new admin
            created_admin_id: ID of created admin
            created_admin_telegram_id: Telegram ID of created admin
            role: Role assigned to new admin
        """
        await self.log_action(
            admin_id=admin.id,
            action_type="ADMIN_CREATED",
            details={
                "created_admin_id": created_admin_id,
                "created_admin_telegram_id": created_admin_telegram_id,
                "role": role,
            },
        )

    async def log_admin_deleted(
        self,
        admin: Admin,
        deleted_admin_id: int,
        deleted_admin_telegram_id: int,
    ) -> None:
        """
        Log admin deletion.

        Args:
            admin: Admin who deleted the admin
            deleted_admin_id: ID of deleted admin
            deleted_admin_telegram_id: Telegram ID of deleted admin
        """
        await self.log_action(
            admin_id=admin.id,
            action_type="ADMIN_DELETED",
            details={
                "deleted_admin_id": deleted_admin_id,
                "deleted_admin_telegram_id": deleted_admin_telegram_id,
            },
        )

    async def log_user_blocked(
        self,
        admin: Admin,
        user_id: int,
        user_telegram_id: int,
        reason: str | None = None,
    ) -> None:
        """
        Log user blocking.

        Args:
            admin: Admin who blocked the user
            user_id: ID of blocked user
            user_telegram_id: Telegram ID of blocked user
            reason: Block reason (optional)
        """
        await self.log_action(
            admin_id=admin.id,
            action_type="USER_BLOCKED",
            target_user_id=user_id,
            details={
                "user_telegram_id": user_telegram_id,
                "reason": reason,
            },
        )

    async def log_user_terminated(
        self,
        admin: Admin,
        user_id: int,
        user_telegram_id: int,
        reason: str | None = None,
    ) -> None:
        """
        Log user termination.

        Args:
            admin: Admin who terminated the user
            user_id: ID of terminated user
            user_telegram_id: Telegram ID of terminated user
            reason: Termination reason (optional)
        """
        await self.log_action(
            admin_id=admin.id,
            action_type="USER_TERMINATED",
            target_user_id=user_id,
            details={
                "user_telegram_id": user_telegram_id,
                "reason": reason,
            },
        )

    async def log_withdrawal_approved(
        self,
        admin: Admin,
        withdrawal_id: int,
        user_id: int,
        amount: str,
    ) -> None:
        """
        Log withdrawal approval.

        Args:
            admin: Admin who approved withdrawal
            withdrawal_id: Withdrawal ID
            user_id: User ID
            amount: Withdrawal amount
        """
        await self.log_action(
            admin_id=admin.id,
            action_type="WITHDRAWAL_APPROVED",
            target_user_id=user_id,
            details={
                "withdrawal_id": withdrawal_id,
                "amount": amount,
            },
        )

    async def log_withdrawal_rejected(
        self,
        admin: Admin,
        withdrawal_id: int,
        user_id: int,
        reason: str | None = None,
    ) -> None:
        """
        Log withdrawal rejection.

        Args:
            admin: Admin who rejected withdrawal
            withdrawal_id: Withdrawal ID
            user_id: User ID
            reason: Rejection reason (optional)
        """
        await self.log_action(
            admin_id=admin.id,
            action_type="WITHDRAWAL_REJECTED",
            target_user_id=user_id,
            details={
                "withdrawal_id": withdrawal_id,
                "reason": reason,
            },
        )

    async def log_broadcast_sent(
        self,
        admin: Admin,
        total_users: int,
        message_preview: str,
    ) -> None:
        """
        Log broadcast message.

        Args:
            admin: Admin who sent broadcast
            total_users: Total users who received message
            message_preview: Preview of message (first 100 chars)
        """
        await self.log_action(
            admin_id=admin.id,
            action_type="BROADCAST_SENT",
            details={
                "total_users": total_users,
                "message_preview": message_preview[:100],
            },
        )

