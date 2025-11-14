"""
Referral service.

Manages referral chains, relationships, and reward processing.
"""

from decimal import Decimal
from typing import Optional

from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import Referral
from app.models.referral_earning import ReferralEarning
from app.models.user import User
from app.repositories.referral_earning_repository import (
    ReferralEarningRepository,
)
from app.repositories.referral_repository import ReferralRepository


# Referral system configuration (from PART2 docs)
REFERRAL_DEPTH = 3
REFERRAL_RATES = {
    1: Decimal("0.03"),  # 3% for level 1
    2: Decimal("0.02"),  # 2% for level 2
    3: Decimal("0.05"),  # 5% for level 3
}


class ReferralService:
    """Referral service for managing referral chains and rewards."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize referral service."""
        self.session = session
        self.referral_repo = ReferralRepository(session)
        self.earning_repo = ReferralEarningRepository(session)

    async def get_referral_chain(
        self, user_id: int, depth: int = REFERRAL_DEPTH
    ) -> list[User]:
        """
        Get referral chain (PostgreSQL CTE optimized).

        Uses recursive CTE to efficiently fetch entire referral chain.

        Args:
            user_id: User ID
            depth: Chain depth to retrieve

        Returns:
            List of users from direct referrer to Nth level
        """
        # Use PostgreSQL recursive CTE for efficient chain retrieval
        query = text("""
            WITH RECURSIVE referral_chain AS (
                -- Base case: start with the user
                SELECT
                    u.id,
                    u.telegram_id,
                    u.username,
                    u.wallet_address,
                    u.referrer_id,
                    u.created_at,
                    u.updated_at,
                    u.is_verified,
                    u.earnings_blocked,
                    u.financial_password_hash,
                    0 AS level
                FROM users u
                WHERE u.id = :user_id

                UNION ALL

                -- Recursive case: get referrer of previous level
                SELECT
                    u.id,
                    u.telegram_id,
                    u.username,
                    u.wallet_address,
                    u.referrer_id,
                    u.created_at,
                    u.updated_at,
                    u.is_verified,
                    u.earnings_blocked,
                    u.financial_password_hash,
                    rc.level + 1 AS level
                FROM users u
                INNER JOIN referral_chain rc ON u.id = rc.referrer_id
                WHERE rc.level < :depth
            )
            SELECT *
            FROM referral_chain
            WHERE level > 0
            ORDER BY level ASC
        """)

        result = await self.session.execute(
            query, {"user_id": user_id, "depth": depth}
        )
        rows = result.fetchall()

        # Map rows to User objects
        chain = []
        for row in rows:
            user = User(
                id=row.id,
                telegram_id=row.telegram_id,
                username=row.username,
                wallet_address=row.wallet_address,
                referrer_id=row.referrer_id,
                is_verified=row.is_verified,
                earnings_blocked=row.earnings_blocked,
            )
            user.created_at = row.created_at
            user.updated_at = row.updated_at
            chain.append(user)

        logger.debug(
            "Referral chain retrieved",
            extra={"user_id": user_id, "depth": depth, "chain_length": len(chain)},
        )

        return chain

    async def create_referral_relationships(
        self, new_user_id: int, direct_referrer_id: int
    ) -> tuple[bool, Optional[str]]:
        """
        Create referral relationships for new user.

        Creates multi-level referral chain (up to REFERRAL_DEPTH levels).

        Args:
            new_user_id: New user ID
            direct_referrer_id: Direct referrer ID

        Returns:
            Tuple of (success, error_message)
        """
        # Self-referral check
        if new_user_id == direct_referrer_id:
            return False, "Нельзя пригласить самого себя"

        # Get direct referrer
        stmt = select(User).where(User.id == direct_referrer_id)
        result = await self.session.execute(stmt)
        direct_referrer = result.scalar_one_or_none()

        if not direct_referrer:
            return False, "Реферер не найден"

        # Get referral chain from direct referrer
        referrers = await self.get_referral_chain(
            direct_referrer_id, REFERRAL_DEPTH
        )

        # Add direct referrer as level 1
        referrers.insert(0, direct_referrer)

        # Check for referral loops
        referrer_ids = [r.id for r in referrers]
        if new_user_id in referrer_ids:
            logger.warning(
                "Referral loop detected",
                extra={
                    "new_user_id": new_user_id,
                    "direct_referrer_id": direct_referrer_id,
                    "chain_ids": referrer_ids,
                },
            )
            return False, "Нельзя создать циклическую реферальную цепочку"

        # Create referral records for each level
        for i, referrer in enumerate(referrers[: REFERRAL_DEPTH]):
            level = i + 1

            # Check if relationship already exists
            existing = await self.referral_repo.find_by(
                referrer_id=referrer.id, referral_id=new_user_id
            )

            if not existing:
                await self.referral_repo.create(
                    referrer_id=referrer.id,
                    referral_id=new_user_id,
                    level=level,
                    total_earned=Decimal("0"),
                )

                logger.debug(
                    "Referral relationship created",
                    extra={
                        "referrer_id": referrer.id,
                        "referral_id": new_user_id,
                        "level": level,
                    },
                )

        await self.session.commit()

        logger.info(
            "Referral chain created",
            extra={
                "new_user_id": new_user_id,
                "direct_referrer_id": direct_referrer_id,
                "levels_created": min(len(referrers), REFERRAL_DEPTH),
            },
        )

        return True, None

    async def process_referral_rewards(
        self, user_id: int, deposit_amount: Decimal
    ) -> tuple[bool, Decimal, Optional[str]]:
        """
        Process referral rewards for a deposit.

        Creates earning records for all referrers in chain.

        Args:
            user_id: User who made deposit
            deposit_amount: Deposit amount

        Returns:
            Tuple of (success, total_rewards, error_message)
        """
        # Get all referral relationships for this user
        relationships = await self.referral_repo.get_referrals_for_user(
            user_id
        )

        if not relationships:
            logger.debug(
                "No referrers found for user", extra={"user_id": user_id}
            )
            return True, Decimal("0"), None

        total_rewards = Decimal("0")

        # Create earning records for each referrer
        for relationship in relationships:
            level = relationship.level
            rate = REFERRAL_RATES.get(level, Decimal("0"))

            if rate == Decimal("0"):
                continue

            reward_amount = deposit_amount * rate

            # Create earning record
            await self.earning_repo.create(
                referral_id=relationship.id,
                amount=reward_amount,
                paid=False,  # Will be paid by payment processor
            )

            # Update total earned in relationship
            relationship.total_earned += reward_amount
            await self.session.flush()

            total_rewards += reward_amount

            logger.info(
                "Referral reward created",
                extra={
                    "referrer_id": relationship.referrer_id,
                    "referral_user_id": user_id,
                    "level": level,
                    "rate": str(rate),
                    "amount": str(reward_amount),
                },
            )

        await self.session.commit()

        return True, total_rewards, None

    async def get_referrals_by_level(
        self, user_id: int, level: int, page: int = 1, limit: int = 10
    ) -> dict:
        """
        Get user's referrals by level.

        Args:
            user_id: User ID
            level: Referral level (1-3)
            page: Page number
            limit: Items per page

        Returns:
            Dict with referrals, total, page, pages
        """
        offset = (page - 1) * limit

        # Get referrals with pagination
        stmt = (
            select(Referral)
            .where(Referral.referrer_id == user_id, Referral.level == level)
            .order_by(Referral.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        relationships = list(result.scalars().all())

        # Get total count
        count_stmt = select(Referral).where(
            Referral.referrer_id == user_id, Referral.level == level
        )
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))

        # Load referral users
        referrals = []
        for rel in relationships:
            user_stmt = select(User).where(User.id == rel.referral_id)
            user_result = await self.session.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if user:
                referrals.append({
                    "user": user,
                    "earned": rel.total_earned,
                    "joined_at": rel.created_at,
                })

        pages = (total + limit - 1) // limit

        return {
            "referrals": referrals,
            "total": total,
            "page": page,
            "pages": pages,
        }

    async def get_pending_earnings(
        self, user_id: int, page: int = 1, limit: int = 10
    ) -> dict:
        """
        Get pending (unpaid) earnings for user.

        Args:
            user_id: User ID
            page: Page number
            limit: Items per page

        Returns:
            Dict with earnings, total, total_amount, page, pages
        """
        # Get user's referral relationships
        relationships = await self.referral_repo.find_by(
            referrer_id=user_id
        )
        relationship_ids = [r.id for r in relationships]

        if not relationship_ids:
            return {
                "earnings": [],
                "total": 0,
                "total_amount": Decimal("0"),
                "page": 1,
                "pages": 0,
            }

        offset = (page - 1) * limit

        # Get unpaid earnings
        earnings = await self.earning_repo.get_unpaid_by_referral_ids(
            relationship_ids, limit=limit, offset=offset
        )

        # Get total count and amount
        all_earnings = await self.earning_repo.get_unpaid_by_referral_ids(
            relationship_ids
        )
        total = len(all_earnings)
        total_amount = sum(e.amount for e in all_earnings)

        pages = (total + limit - 1) // limit

        return {
            "earnings": earnings,
            "total": total,
            "total_amount": total_amount,
            "page": page,
            "pages": pages,
        }

    async def mark_earning_as_paid(
        self, earning_id: int, tx_hash: str
    ) -> tuple[bool, Optional[str]]:
        """
        Mark earning as paid (called by payment processor).

        Args:
            earning_id: Earning ID
            tx_hash: Transaction hash

        Returns:
            Tuple of (success, error_message)
        """
        earning = await self.earning_repo.get_by_id(earning_id)

        if not earning:
            return False, "Earning not found"

        if earning.paid:
            return False, "Already paid"

        await self.earning_repo.update(
            earning_id, paid=True, tx_hash=tx_hash
        )

        await self.session.commit()

        logger.info(
            "Earning marked as paid",
            extra={
                "earning_id": earning_id,
                "amount": str(earning.amount),
                "tx_hash": tx_hash,
            },
        )

        return True, None
