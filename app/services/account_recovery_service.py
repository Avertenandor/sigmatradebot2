"""
Account recovery service.

R16-3: Handles recovery of lost Telegram account access.
"""

from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.blacklist_service import BlacklistService
from app.models.blacklist import BlacklistActionType


class AccountRecoveryService:
    """
    R16-3: Account recovery service.

    Handles recovery of access when user loses Telegram account.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize account recovery service."""
        self.session = session
        self.user_repo = UserRepository(session)
        self.blacklist_service = BlacklistService(session)

    async def verify_wallet_ownership(
        self, wallet_address: str, signature: str, message: str
    ) -> tuple[bool, User | None]:
        """
        Verify wallet ownership through signature.

        R16-3: User must sign a message with their private key.

        Args:
            wallet_address: Wallet address
            signature: Signature of the message
            message: Original message that was signed

        Returns:
            Tuple of (is_valid, user)
        """
        try:
            from eth_account import Account
            from eth_account.messages import encode_defunct

            # Recover address from signature
            message_hash = encode_defunct(text=message)
            recovered_address = Account.recover_message(
                message_hash, signature=signature
            )

            # Normalize addresses (lowercase)
            recovered_lower = recovered_address.lower()
            wallet_lower = wallet_address.lower()

            if recovered_lower != wallet_lower:
                logger.warning(
                    f"Wallet ownership verification failed: "
                    f"recovered {recovered_address}, expected {wallet_address}"
                )
                return False, None

            # Find user by wallet
            user = await self.user_repo.get_by_wallet_address(wallet_address)

            if not user:
                logger.warning(
                    f"User not found for wallet {wallet_address}"
                )
                return False, None

            logger.info(
                f"Wallet ownership verified for user {user.id}, "
                f"wallet {wallet_address}"
            )
            return True, user

        except Exception as e:
            logger.error(f"Error verifying wallet ownership: {e}")
            return False, None

    async def initiate_recovery(
        self,
        new_telegram_id: int,
        wallet_address: str,
        signature: str,
        message: str,
        additional_info: dict[str, Any] | None = None,
    ) -> tuple[bool, User | None, str | None]:
        """
        Initiate account recovery process.

        R16-3: Main recovery flow.

        Args:
            new_telegram_id: New Telegram ID
            wallet_address: User's wallet address
            signature: Signature proving wallet ownership
            message: Message that was signed
            additional_info: Additional verification info (email, phone, etc.)

        Returns:
            Tuple of (success, user, error_message)
        """
        # Step 1: Verify wallet ownership
        is_valid, user = await self.verify_wallet_ownership(
            wallet_address, signature, message
        )

        if not is_valid or not user:
            return False, None, "Не удалось подтвердить владение кошельком"

        # Step 2: Check if new telegram_id is already in use
        existing_user = await self.user_repo.get_by_telegram_id(new_telegram_id)
        if existing_user and existing_user.id != user.id:
            return (
                False,
                None,
                "Этот Telegram аккаунт уже привязан к другому пользователю",
            )

        # Step 3: Additional verification (if provided)
        if additional_info:
            # Verify email/phone if provided
            if "email" in additional_info:
                if user.email != additional_info["email"]:
                    return False, None, "Email не совпадает"

            if "phone" in additional_info:
                if user.phone != additional_info["phone"]:
                    return False, None, "Телефон не совпадает"

        # Step 4: Check for suspicious activity
        # (This would be done by admin review in production)
        logger.info(
            f"R16-3: Account recovery proceeding: user_id={user.id}, "
            f"old_telegram_id={user.telegram_id}, new_telegram_id={new_telegram_id}, "
            f"wallet={wallet_address}"
        )

        # Step 5: Migrate account
        old_telegram_id = user.telegram_id

        # Block old telegram_id
        logger.info(
            f"R16-3: Blocking old telegram_id for account recovery: "
            f"old_telegram_id={old_telegram_id}, user_id={user.id}"
        )
        await self.blacklist_service.add_to_blacklist(
            telegram_id=old_telegram_id,
            reason="Account migrated to new Telegram ID",
            action_type=BlacklistActionType.REGISTRATION_DENIED.value,
        )

        # Update user with new telegram_id
        await self.user_repo.update(
            user.id,
            telegram_id=new_telegram_id,
        )

        # Generate new financial password (security requirement)
        import secrets
        import string
        import bcrypt

        new_finpass = "".join(
            secrets.choice(string.ascii_letters + string.digits)
            for _ in range(12)
        )
        hashed_finpass = bcrypt.hashpw(
            new_finpass.encode(), bcrypt.gensalt()
        ).decode()

        await self.user_repo.update(
            user.id,
            financial_password=hashed_finpass,
        )

        await self.session.commit()

        logger.info(
            f"R16-3: Account recovery completed successfully: "
            f"user_id={user.id}, "
            f"old_telegram_id={old_telegram_id}, "
            f"new_telegram_id={new_telegram_id}, "
            f"wallet={wallet_address}, "
            f"has_deposits={len(user.deposits) > 0 if hasattr(user, 'deposits') else False}, "
            f"balance={user.balance if hasattr(user, 'balance') else 0}"
        )

        # Return success, user, and new financial password
        return True, user, new_finpass

    async def get_recovery_info(self, wallet_address: str) -> dict[str, Any] | None:
        """
        Get recovery information for wallet (for verification).

        Args:
            wallet_address: Wallet address

        Returns:
            Dict with recovery info or None
        """
        user = await self.user_repo.get_by_wallet_address(wallet_address)

        if not user:
            return None

        # Return partial info for verification (not sensitive)
        return {
            "has_deposits": len(user.deposits) > 0 if hasattr(user, "deposits") else False,
            "has_balance": user.balance > 0,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            # Don't return sensitive info like email/phone directly
        }

