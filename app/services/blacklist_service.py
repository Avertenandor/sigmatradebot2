"""
Blacklist Service.

Manages user blacklist for pre-registration and ban prevention.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blacklist import Blacklist, BlacklistActionType
from app.repositories.blacklist_repository import BlacklistRepository


class BlacklistService:
    """
    Service for managing blacklist.

    Features:
    - Add/remove from blacklist
    - Check if user is blacklisted
    - Reason tracking
    - Admin logging
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize blacklist service.

        Args:
            session: Database session
        """
        self.session = session
        self.repository = BlacklistRepository(session)

    async def is_blacklisted(
        self,
        telegram_id: int | None = None,
        wallet_address: str | None = None,
    ) -> bool:
        """
        Check if user is blacklisted.

        Args:
            telegram_id: Telegram user ID
            wallet_address: Wallet address

        Returns:
            True if blacklisted
        """
        if telegram_id:
            entry = await self.repository.find_by_telegram_id(telegram_id)
            if entry and entry.is_active:
                return True

        if wallet_address:
            entry = await self.repository.find_by_wallet(
                wallet_address.lower()
            )
            if entry and entry.is_active:
                return True

        return False

    async def add_to_blacklist(
        self,
        telegram_id: int | None = None,
        wallet_address: str | None = None,
        reason: str = "Manual blacklist",
        added_by_admin_id: int | None = None,
        action_type: str = "registration_denied",
    ) -> Blacklist:
        """
        Add user to blacklist.

        Args:
            telegram_id: Telegram user ID
            wallet_address: Wallet address
            reason: Blacklist reason
            added_by_admin_id: Admin who added
            action_type: Type of blacklist action

        Returns:
            Blacklist entry

        Raises:
            ValueError: If neither telegram_id nor wallet_address provided
        """
        if not telegram_id and not wallet_address:
            raise ValueError(
                "Either telegram_id or wallet_address must be provided"
            )

        # Normalize wallet address
        if wallet_address:
            wallet_address = wallet_address.lower()

        # Check if already blacklisted
        existing = None

        if telegram_id:
            existing = await self.repository.find_by_telegram_id(telegram_id)

        if not existing and wallet_address:
            existing = await self.repository.find_by_wallet(wallet_address)

        if existing:
            # Reactivate if inactive
            if not existing.is_active:
                existing.is_active = True
                existing.reason = reason
                existing.created_by_admin_id = added_by_admin_id
                existing.action_type = action_type
                existing.created_at = datetime.now(UTC)

                # Update appeal deadline for blocked users
                if action_type == BlacklistActionType.BLOCKED:
                    appeal_deadline = (
                        datetime.now(UTC) + timedelta(days=3)
                    )
                else:
                    appeal_deadline = None

                update_data = {
                    "action_type": action_type,
                    "created_at": datetime.now(UTC),
                    "appeal_deadline": appeal_deadline,
                    "is_active": True,
                }
                if wallet_address:
                    update_data["wallet_address"] = wallet_address
                await self.repository.update(
                    existing.id,
                    **update_data
                )

                logger.info(
                    f"Reactivated blacklist entry: "
                    f"telegram_id={telegram_id}, "
                    f"wallet={wallet_address}"
                )

                return existing

            # Already active
            logger.warning(
                f"User already blacklisted: "
                f"telegram_id={telegram_id}, "
                f"wallet={wallet_address}"
            )
            return existing

        # Calculate appeal deadline for blocked users (3 working days)
        appeal_deadline = None
        if action_type == BlacklistActionType.BLOCKED:
            # 3 working days = 3 calendar days (simplified)
            appeal_deadline = (
                datetime.now(UTC) + timedelta(days=3)
            )

        # Create new entry
        create_data = {
            "telegram_id": telegram_id,
            "reason": reason,
            "created_by_admin_id": added_by_admin_id,
            "action_type": action_type,
            "appeal_deadline": appeal_deadline,
            "is_active": True,
        }
        if wallet_address:
            create_data["wallet_address"] = wallet_address
        entry = await self.repository.create(**create_data)

        logger.info(
            f"Added to blacklist: "
            f"telegram_id={telegram_id}, "
            f"wallet={wallet_address}, "
            f"reason={reason}"
        )

        return entry

    async def remove_from_blacklist(
        self,
        telegram_id: int | None = None,
        wallet_address: str | None = None,
    ) -> bool:
        """
        Remove user from blacklist.

        Args:
            telegram_id: Telegram user ID
            wallet_address: Wallet address

        Returns:
            True if removed
        """
        if not telegram_id and not wallet_address:
            return False

        # Normalize wallet
        if wallet_address:
            wallet_address = wallet_address.lower()

        # Find entry
        entry = None

        if telegram_id:
            entry = await self.repository.find_by_telegram_id(telegram_id)

        if not entry and wallet_address:
            entry = await self.repository.find_by_wallet(wallet_address)

        if not entry:
            logger.warning(
                f"Blacklist entry not found: "
                f"telegram_id={telegram_id}, "
                f"wallet={wallet_address}"
            )
            return False

        # Deactivate instead of delete
        await self.repository.update(
            entry.id,
            is_active=False,
        )

        logger.info(
            f"Removed from blacklist: "
            f"telegram_id={telegram_id}, "
            f"wallet={wallet_address}"
        )

        return True

    async def get_blacklist_entry(
        self,
        telegram_id: int | None = None,
        wallet_address: str | None = None,
    ) -> Blacklist | None:
        """
        Get blacklist entry.

        Args:
            telegram_id: Telegram user ID
            wallet_address: Wallet address

        Returns:
            Blacklist entry or None
        """
        if telegram_id:
            return await self.repository.find_by_telegram_id(telegram_id)

        if wallet_address:
            return await self.repository.find_by_wallet(
                wallet_address.lower()
            )

        return None

    async def get_all_active(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Blacklist]:
        """
        Get all active blacklist entries.

        Args:
            limit: Maximum entries to return
            offset: Offset for pagination

        Returns:
            List of Blacklist entries
        """
        return await self.repository.get_active_blacklist(
            limit=limit,
            offset=offset,
        )

    async def count_active(self) -> int:
        """
        Count active blacklist entries.

        Returns:
            Number of active entries
        """
        return await self.repository.count_active()

    async def terminate_user(
        self, user_id: int, reason: str, admin_id: int | None = None
    ) -> dict:
        """
        Terminate user account (R15-2): BLOCKED → TERMINATED.

        Atomic transition with handling of all consequences:
        - Reject all pending appeals
        - Reject all pending support tickets
        - Stop ROI distribution (already handled by is_banned)
        - Reject all pending withdrawals
        - Clear notification queue

        Args:
            user_id: User ID
            reason: Termination reason
            admin_id: Admin ID (optional)

        Returns:
            Dict with success status and actions taken
        """
        from datetime import UTC, datetime

        from app.models.appeal import Appeal, AppealStatus
        from app.models.enums import (
            SupportTicketStatus,
            TransactionStatus,
            TransactionType,
        )
        from app.repositories.appeal_repository import AppealRepository
        from app.repositories.support_ticket_repository import (
            SupportTicketRepository,
        )
        from app.repositories.transaction_repository import (
            TransactionRepository,
        )
        from app.repositories.user_repository import UserRepository

        user_repo = UserRepository(self.session)
        transaction_repo = TransactionRepository(self.session)
        appeal_repo = AppealRepository(self.session)
        ticket_repo = SupportTicketRepository(self.session)

        user = await user_repo.get_by_id(user_id)
        if not user:
            return {
                "success": False,
                "error": "User not found",
            }

        actions_taken = []

        # 1. Reject all pending appeals
        pending_appeals = await appeal_repo.find_by(
            user_id=user_id,
            status=AppealStatus.PENDING,
        )
        for appeal in pending_appeals:
            appeal.status = AppealStatus.REJECTED.value
            appeal.reviewed_at = datetime.now(UTC)
            appeal.review_notes = (
                "Автоматически отклонено при терминации аккаунта"
            )
            actions_taken.append(f"Rejected appeal {appeal.id}")

        # 2. Reject all pending support tickets
        pending_tickets = await ticket_repo.find_by(
            user_id=user_id,
            status=SupportTicketStatus.OPEN.value,
        )
        for ticket in pending_tickets:
            ticket.status = SupportTicketStatus.CLOSED.value
            actions_taken.append(f"Closed support ticket {ticket.id}")

        # 3. Reject all pending withdrawals
        pending_withdrawals = await transaction_repo.get_by_user(
            user_id=user_id,
            type=TransactionType.WITHDRAWAL.value,
            status=TransactionStatus.PENDING.value,
        )
        rejected_count = 0
        for withdrawal in pending_withdrawals:
            withdrawal.status = TransactionStatus.FAILED.value
            # Return balance
            user.balance = user.balance + withdrawal.amount
            rejected_count += 1

        if rejected_count > 0:
            actions_taken.append(f"Rejected {rejected_count} pending withdrawals")

        # 4. Update blacklist entry to TERMINATED
        blacklist_entry = await self.repository.find_by_telegram_id(
            user.telegram_id
        )
        if blacklist_entry:
            await self.repository.update(
                blacklist_entry.id,
                action_type=BlacklistActionType.TERMINATED,
                reason=reason,
            )
            actions_taken.append("Updated blacklist to TERMINATED")

        # 6. Mark user as banned (already done, but ensure it's set)
        user.is_banned = True
        await user_repo.update(user_id, is_banned=True)

        await self.session.commit()

        logger.warning(
            f"User {user_id} terminated",
            extra={
                "user_id": user_id,
                "telegram_id": user.telegram_id,
                "rejected_appeals": len(pending_appeals),
                "closed_tickets": len(pending_tickets),
                "rejected_withdrawals": rejected_count,
                "reason": reason,
            },
        )

        return {
            "success": True,
            "user_id": user_id,
            "actions_taken": actions_taken,
            "rejected_appeals": len(pending_appeals),
            "closed_tickets": len(pending_tickets),
            "rejected_withdrawals": rejected_count,
        }

    async def block_user_with_active_operations(
        self,
        user_id: int,
        reason: str,
        admin_id: int | None = None,
        redis_client: Any | None = None,
    ) -> dict:
        """
        Block user and handle active operations (R15-1, R15-4).

        R15-4: Uses distributed lock to prevent race conditions.

        Policy:
        - Stop ROI distribution
        - Freeze pending withdrawals (mark as FROZEN)
        - Continue referral earnings (not blocked)

        Args:
            user_id: User ID
            reason: Block reason
            admin_id: Admin ID (optional)
            redis_client: Optional Redis client for distributed lock

        Returns:
            Dict with success status and actions taken
        """
        # R15-4: Use distributed lock to prevent race conditions
        from app.utils.distributed_lock import get_distributed_lock

        lock = get_distributed_lock(
            redis_client=redis_client, session=self.session
        )
        lock_key = f"user:{user_id}:block_operation"

        async with lock.lock(lock_key, timeout=30, blocking=True, blocking_timeout=5.0) as acquired:
            if not acquired:
                logger.warning(
                    f"Could not acquire lock for blocking user {user_id}, "
                    "operation may be in progress"
                )
                return {
                    "success": False,
                    "error": "Operation already in progress",
                    "actions_taken": [],
                }

            from app.models.enums import TransactionStatus, TransactionType
            from app.repositories.deposit_repository import DepositRepository
            from app.repositories.transaction_repository import (
                TransactionRepository,
            )
            from app.repositories.user_repository import UserRepository

            user_repo = UserRepository(self.session)
            transaction_repo = TransactionRepository(self.session)
            deposit_repo = DepositRepository(self.session)

            user = await user_repo.get_by_id(user_id)
            if not user:
                return {
                    "success": False,
                    "error": "User not found",
                }

            actions_taken = []

            # 1. Freeze pending withdrawals
            pending_withdrawals = await transaction_repo.get_by_user(
                user_id=user_id,
                type=TransactionType.WITHDRAWAL.value,
                status=TransactionStatus.PENDING.value,
            )

            frozen_count = 0
            for withdrawal in pending_withdrawals:
                withdrawal.status = TransactionStatus.FROZEN.value
                frozen_count += 1

            if frozen_count > 0:
                actions_taken.append(f"Frozen {frozen_count} pending withdrawals")

            # 2. Mark user as banned and block earnings (stop ROI distribution)
            user.is_banned = True
            await user_repo.update(
                user_id, is_banned=True, earnings_blocked=True
            )

            # 3. Add to blacklist
            await self.add_to_blacklist(
                telegram_id=user.telegram_id,
                wallet_address=user.wallet_address,
                reason=reason,
                added_by_admin_id=admin_id,
                action_type=BlacklistActionType.BLOCKED,
            )

            await self.session.commit()

            logger.warning(
                f"User {user_id} blocked with active operations",
                extra={
                    "user_id": user_id,
                    "telegram_id": user.telegram_id,
                    "frozen_withdrawals": frozen_count,
                    "reason": reason,
                },
            )

            return {
                "success": True,
                "user_id": user_id,
                "actions_taken": actions_taken,
                "frozen_withdrawals": frozen_count,
            }