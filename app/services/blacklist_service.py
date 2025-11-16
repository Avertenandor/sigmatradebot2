"""
Blacklist Service.

Manages user blacklist for pre-registration and ban prevention.
"""

from datetime import datetime, timedelta
from typing import Optional

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
        telegram_id: Optional[int] = None,
        wallet_address: Optional[str] = None,
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
        telegram_id: Optional[int] = None,
        wallet_address: Optional[str] = None,
        reason: str = "Manual blacklist",
        added_by_admin_id: Optional[int] = None,
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
                existing.created_at = datetime.utcnow()
                
                # Update appeal deadline for blocked users
                if action_type == BlacklistActionType.BLOCKED:
                    existing.appeal_deadline = datetime.utcnow() + timedelta(days=3)
                else:
                    existing.appeal_deadline = None

                await self.repository.update(existing)

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
            appeal_deadline = datetime.utcnow() + timedelta(days=3)
        
        # Create new entry (wallet_address not stored in Blacklist model, only telegram_id)
        entry = await self.repository.create(
            {
                "telegram_id": telegram_id,
                "reason": reason,
                "created_by_admin_id": added_by_admin_id,
                "action_type": action_type,
                "appeal_deadline": appeal_deadline,
                "is_active": True,
            }
        )

        logger.info(
            f"Added to blacklist: "
            f"telegram_id={telegram_id}, "
            f"wallet={wallet_address}, "
            f"reason={reason}"
        )

        return entry

    async def remove_from_blacklist(
        self,
        telegram_id: Optional[int] = None,
        wallet_address: Optional[str] = None,
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
        entry.is_active = False
        await self.repository.update(entry)

        logger.info(
            f"Removed from blacklist: "
            f"telegram_id={telegram_id}, "
            f"wallet={wallet_address}"
        )

        return True

    async def get_blacklist_entry(
        self,
        telegram_id: Optional[int] = None,
        wallet_address: Optional[str] = None,
    ) -> Optional[Blacklist]:
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
