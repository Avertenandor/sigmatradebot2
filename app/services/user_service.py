"""
User service.

Business logic for user management.
"""

from decimal import Decimal

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.blacklist_repository import (
    BlacklistRepository,
)
from app.repositories.user_repository import UserRepository
from app.services.referral_service import ReferralService


class UserService:
    """
    User service.

    Handles user registration, profile management, and referrals.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize user service.

        Args:
            session: Database session
        """
        self.session = session
        self.user_repo = UserRepository(session)
        self.blacklist_repo = BlacklistRepository(session)
        self.referral_service = ReferralService(session)

    async def get_by_id(self, user_id: int) -> User | None:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User or None
        """
        return await self.user_repo.get_by_id(user_id)

    async def get_by_telegram_id(
        self, telegram_id: int
    ) -> User | None:
        """
        Get user by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            User or None
        """
        return await self.user_repo.get_by_telegram_id(
            telegram_id
        )

    async def register_user(
        self,
        telegram_id: int,
        wallet_address: str,
        financial_password: str,
        username: str | None = None,
        referrer_telegram_id: int | None = None,
    ) -> User:
        """
        Register new user with referral support.

        Args:
            telegram_id: Telegram user ID
            wallet_address: User's wallet address
            financial_password: Bcrypt-hashed password
            username: Telegram username (optional)
            referrer_telegram_id: Referrer's Telegram ID

        Returns:
            Created user

        Raises:
            ValueError: If user already exists or blacklisted
        """
        # Check if blacklisted
        blacklist_entry = await self.blacklist_repo.get_by_telegram_id(
            telegram_id
        )
        if blacklist_entry and blacklist_entry.is_active:
            # Raise specific error with action type for proper message handling
            raise ValueError(
                f"BLACKLISTED:"
                f"{blacklist_entry.action_type or 'REGISTRATION_DENIED'}"
            )

        # Check if already exists
        existing = await self.user_repo.get_by_telegram_id(
            telegram_id
        )
        if existing:
            raise ValueError("User already registered")

        # Find referrer if provided
        referrer_id = None
        if referrer_telegram_id:
            referrer = await self.user_repo.get_by_telegram_id(
                referrer_telegram_id
            )
            if referrer:
                referrer_id = referrer.id

        # Create user
        user = await self.user_repo.create(
            telegram_id=telegram_id,
            username=username,
            wallet_address=wallet_address,
            financial_password=financial_password,
            referrer_id=referrer_id,
        )

        await self.session.commit()

        # Create referral relationships if referrer exists
        if referrer_id:
            result = (
                await self.referral_service.create_referral_relationships(
                    new_user_id=user.id,
                    direct_referrer_id=referrer_id,
                )
            )
            success, error_msg = result
            if not success:
                logger.warning(
                    "Failed to create referral relationships",
                    extra={
                        "new_user_id": user.id,
                        "referrer_id": referrer_id,
                        "error": error_msg,
                    },
                )
            else:
                logger.info(
                    "Referral relationships created",
                    extra={
                        "new_user_id": user.id,
                        "referrer_id": referrer_id,
                    },
                )

        logger.info(
            "User registered",
            extra={
                "user_id": user.id,
                "telegram_id": telegram_id,
                "has_referrer": referrer_id is not None,
            },
        )

        return user

    async def update_profile(
        self, user_id: int, **data
    ) -> User | None:
        """
        Update user profile.

        Args:
            user_id: User ID
            **data: Fields to update

        Returns:
            Updated user or None
        """
        user = await self.user_repo.update(user_id, **data)

        if user:
            await self.session.commit()
            logger.info(
                "User profile updated",
                extra={"user_id": user_id},
            )

        return user

    async def block_earnings(
        self, user_id: int, block: bool = True
    ) -> User | None:
        """
        Block/unblock user earnings.

        Used during financial password recovery.

        Args:
            user_id: User ID
            block: True to block, False to unblock

        Returns:
            Updated user or None
        """
        return await self.update_profile(
            user_id, earnings_blocked=block
        )

    async def ban_user(
        self, user_id: int, ban: bool = True
    ) -> User | None:
        """
        Ban/unban user.

        Args:
            user_id: User ID
            ban: True to ban, False to unban

        Returns:
            Updated user or None
        """
        return await self.update_profile(user_id, is_banned=ban)

    async def get_all_telegram_ids(self) -> list[int]:
        """
        Get all user Telegram IDs.

        Returns:
            List of Telegram IDs
        """
        return await self.user_repo.get_all_telegram_ids()

    async def verify_financial_password(
        self, user_id: int, password: str
    ) -> bool:
        """
        Verify financial password.

        Args:
            user_id: User ID
            password: Plain password to verify

        Returns:
            True if password matches
        """
        import bcrypt

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return False

        return bcrypt.checkpw(
            password.encode(),
            user.financial_password.encode(),
        )

    async def unban_user(self, user_id: int) -> dict:
        """
        Unban user.

        Args:
            user_id: User ID

        Returns:
            Result dict with success status
        """
        user = await self.ban_user(user_id, ban=False)
        if user:
            return {"success": True}
        return {"success": False, "error": "User not found"}

    async def get_total_users(self) -> int:
        """
        Get total number of users.

        Returns:
            Total user count
        """
        return await self.user_repo.count()

    async def get_verified_users(self) -> int:
        """
        Get number of verified users.

        Returns:
            Verified user count
        """
        users = await self.user_repo.find_by(is_verified=True)
        return len(users)

    async def get_user_stats(self, user_id: int) -> dict:
        """
        Get user statistics.

        Args:
            user_id: User ID

        Returns:
            User stats dict
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return {}

        # Get deposits total (stub - should query deposits)
        total_deposits = Decimal("0.00")

        # Get referral count (stub - should query referrals)
        referral_count = 0

        # Get activated levels (stub - should query deposits)
        activated_levels = []

        return {
            "total_deposits": total_deposits,
            "referral_count": referral_count,
            "activated_levels": activated_levels,
        }

    async def get_user_balance(self, user_id: int) -> dict:
        """
        Get user balance with detailed statistics.

        Args:
            user_id: User ID

        Returns:
            Balance dict with all statistics
        """
        from app.models.enums import TransactionStatus, TransactionType
        from app.repositories.deposit_repository import DepositRepository
        from app.repositories.transaction_repository import (
            TransactionRepository,
        )

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return {
                "available_balance": Decimal("0.00"),
                "total_balance": Decimal("0.00"),
                "total_earned": Decimal("0.00"),
                "pending_earnings": Decimal("0.00"),
                "pending_withdrawals": Decimal("0.00"),
                "total_deposits": Decimal("0.00"),
                "total_withdrawals": Decimal("0.00"),
                "total_earnings": Decimal("0.00"),
            }

        # Get deposits total
        deposit_repo = DepositRepository(self.session)
        total_deposits = await deposit_repo.get_total_deposited(user_id)

        # Get withdrawals total
        transaction_repo = TransactionRepository(self.session)
        withdrawals = await transaction_repo.get_by_user(
            user_id=user_id,
            type=TransactionType.WITHDRAWAL.value,
            status=TransactionStatus.CONFIRMED.value,
        )
        total_withdrawals = (
            sum(w.amount for w in withdrawals)
            if withdrawals else Decimal("0.00")
        )

        # Get pending withdrawals
        pending_withdrawals_list = await transaction_repo.get_by_user(
            user_id=user_id,
            type=TransactionType.WITHDRAWAL.value,
            status=TransactionStatus.PENDING.value,
        )
        pending_withdrawals = (
            sum(w.amount for w in pending_withdrawals_list)
            if pending_withdrawals_list else Decimal("0.00")
        )

        # Get earnings (deposit rewards + referral earnings)
        earnings_transactions = await transaction_repo.get_by_user(
            user_id=user_id,
            type=TransactionType.DEPOSIT_REWARD.value,
            status=TransactionStatus.CONFIRMED.value,
        )
        total_earnings = (
            sum(e.amount for e in earnings_transactions)
            if earnings_transactions else Decimal("0.00")
        )

        # Add referral earnings if any
        referral_earnings = await transaction_repo.get_by_user(
            user_id=user_id,
            type=TransactionType.REFERRAL_REWARD.value,
            status=TransactionStatus.CONFIRMED.value,
        )
        if referral_earnings:
            total_earnings += sum(e.amount for e in referral_earnings)

        # Calculate total balance (available + pending earnings)
        available_balance = getattr(user, "balance", Decimal("0.00"))
        pending_earnings = getattr(user, "pending_earnings", Decimal("0.00"))
        total_balance = available_balance + pending_earnings

        return {
            "available_balance": available_balance,
            "total_balance": total_balance,
            "total_earned": getattr(user, "total_earned", Decimal("0.00")),
            "pending_earnings": pending_earnings,
            "pending_withdrawals": pending_withdrawals,
            "total_deposits": total_deposits,
            "total_withdrawals": total_withdrawals,
            "total_earnings": total_earnings,
        }

    def generate_referral_link(self, user_id: int, bot_username: str) -> str:
        """
        Generate referral link for user.

        Args:
            user_id: User ID
            bot_username: Bot username

        Returns:
            Referral link
        """
        return f"https://t.me/{bot_username}?start=ref_{user_id}"

    async def find_by_id(self, user_id: int) -> User | None:
        """
        Find user by ID (alias for get_by_id).

        Args:
            user_id: User ID

        Returns:
            User or None
        """
        return await self.user_repo.get_by_id(user_id)

    async def find_by_username(self, username: str) -> User | None:
        """
        Find user by username.

        Args:
            username: Username (without @)

        Returns:
            User or None
        """
        users = await self.user_repo.find_by(username=username)
        return users[0] if users else None

    async def find_by_telegram_id(self, telegram_id: int) -> User | None:
        """
        Find user by Telegram ID.

        Args:
            telegram_id: Telegram ID

        Returns:
            User or None
        """
        users = await self.user_repo.find_by(telegram_id=telegram_id)
        return users[0] if users else None

    async def get_by_wallet(self, wallet_address: str) -> User | None:
        """
        Get user by wallet address.

        Args:
            wallet_address: Wallet address

        Returns:
            User or None
        """
        return await self.user_repo.get_by_wallet_address(wallet_address)
