"""
Referral service.

Manages referral chains, relationships, and reward processing.
"""

from decimal import Decimal

from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import Referral
from app.models.user import User
from app.repositories.referral_earning_repository import (
    ReferralEarningRepository,
)
from app.repositories.referral_repository import ReferralRepository
from app.repositories.user_repository import UserRepository

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
        self.user_repo = UserRepository(session)

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
                    u.financial_password,
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
                    u.financial_password,
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
                financial_password=row.financial_password,
            )
            user.created_at = row.created_at
            user.updated_at = row.updated_at
            chain.append(user)

        logger.debug(
            "Referral chain retrieved",
            extra={
                "user_id": user_id,
                "depth": depth,
                "chain_length": len(chain)
            },
        )

        return chain

    async def create_referral_relationships(
        self, new_user_id: int, direct_referrer_id: int
    ) -> tuple[bool, str | None]:
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
    ) -> tuple[bool, Decimal, str | None]:
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

            # Fetch referrer to update balance
            referrer = await self.user_repo.get_by_id(relationship.referrer_id)
            if not referrer:
                logger.warning(
                    f"Referrer {relationship.referrer_id} not found for reward",
                    extra={"referral_id": relationship.id}
                )
                continue

            # Update referrer balance
            referrer.balance += reward_amount
            referrer.total_earned += reward_amount
            self.session.add(referrer)

            # Create earning record
            await self.earning_repo.create(
                referral_id=relationship.id,
                amount=reward_amount,
                paid=True,  # Paid to internal balance
                tx_hash='internal_balance',
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
                    "source": "deposit",
                },
            )

        await self.session.commit()

        return True, total_rewards, None

    async def process_roi_referral_rewards(
        self, user_id: int, roi_amount: Decimal
    ) -> tuple[bool, Decimal, str | None]:
        """
        Process referral rewards for ROI accrual.

        Args:
            user_id: User who received ROI
            roi_amount: ROI amount

        Returns:
            Tuple of (success, total_rewards, error_message)
        """
        # Get all referral relationships for this user
        relationships = await self.referral_repo.get_referrals_for_user(
            user_id
        )

        if not relationships:
            return True, Decimal("0"), None

        total_rewards = Decimal("0")

        # Create earning records for each referrer
        for relationship in relationships:
            level = relationship.level
            rate = REFERRAL_RATES.get(level, Decimal("0"))

            if rate == Decimal("0"):
                continue

            # Reward is % of ROI amount
            reward_amount = roi_amount * rate

            if reward_amount <= 0:
                continue

            # Fetch referrer to update balance
            referrer = await self.user_repo.get_by_id(relationship.referrer_id)
            if not referrer:
                continue

            # Update referrer balance
            referrer.balance += reward_amount
            referrer.total_earned += reward_amount
            self.session.add(referrer)

            # Create earning record
            await self.earning_repo.create(
                referral_id=relationship.id,
                amount=reward_amount,
                paid=True,  # Paid to internal balance
                tx_hash='internal_balance_roi',
            )

            # Update total earned in relationship
            relationship.total_earned += reward_amount
            self.session.add(relationship)

            total_rewards += reward_amount

            logger.info(
                "Referral ROI reward created",
                extra={
                    "referrer_id": relationship.referrer_id,
                    "referral_user_id": user_id,
                    "level": level,
                    "rate": str(rate),
                    "amount": str(reward_amount),
                    "source": "roi",
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
    ) -> tuple[bool, str | None]:
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

    async def get_referral_stats(self, user_id: int) -> dict:
        """
        Get referral statistics for user.

        Args:
            user_id: User ID

        Returns:
            Dict with referral counts and earnings
        """
        # Get all referral relationships
        all_relationships = await self.referral_repo.find_by(
            referrer_id=user_id
        )

        # Count by level
        direct_referrals = sum(1 for r in all_relationships if r.level == 1)
        level2_referrals = sum(1 for r in all_relationships if r.level == 2)
        level3_referrals = sum(1 for r in all_relationships if r.level == 3)

        # Calculate earnings
        relationship_ids = [r.id for r in all_relationships]

        if relationship_ids:
            all_earnings = await self.earning_repo.find_by_referral_ids(
                relationship_ids
            )
            total_earned = sum(e.amount for e in all_earnings)
            paid_earnings = sum(e.amount for e in all_earnings if e.paid)
            pending_earnings = sum(
                e.amount for e in all_earnings if not e.paid
            )
        else:
            total_earned = Decimal("0")
            paid_earnings = Decimal("0")
            pending_earnings = Decimal("0")

        return {
            "direct_referrals": direct_referrals,
            "level2_referrals": level2_referrals,
            "level3_referrals": level3_referrals,
            "total_earned": total_earned,
            "pending_earnings": pending_earnings,
            "paid_earnings": paid_earnings,
        }

    async def get_referral_leaderboard(self, limit: int = 10) -> dict:
        """
        Get referral leaderboard.

        Args:
            limit: Number of top users to return

        Returns:
            Dict with by_referrals and by_earnings lists
        """
        # Get all users with referrals
        stmt = text("""
            WITH referral_stats AS (
                SELECT
                    r.referrer_id,
                    COUNT(DISTINCT r.referral_id) as referral_count,
                    COALESCE(SUM(re.amount), 0) as total_earnings
                FROM referrals r
                LEFT JOIN referral_earnings re ON re.referral_id = r.id
                GROUP BY r.referrer_id
            )
            SELECT
                u.id as user_id,
                u.telegram_id,
                u.username,
                rs.referral_count,
                rs.total_earnings
            FROM referral_stats rs
            JOIN users u ON u.id = rs.referrer_id
            ORDER BY rs.referral_count DESC, rs.total_earnings DESC
        """)

        result = await self.session.execute(stmt)
        rows = result.fetchall()

        # Build by_referrals leaderboard
        by_referrals = []
        for idx, row in enumerate(rows[:limit], 1):
            by_referrals.append({
                "rank": idx,
                "user_id": row.user_id,
                "telegram_id": row.telegram_id,
                "username": row.username,
                "referral_count": row.referral_count,
                "total_earnings": Decimal(str(row.total_earnings)),
            })

        # Build by_earnings leaderboard (sorted differently)
        sorted_by_earnings = sorted(
            rows,
            key=lambda r: (r.total_earnings, r.referral_count),
            reverse=True
        )
        by_earnings = []
        for idx, row in enumerate(sorted_by_earnings[:limit], 1):
            by_earnings.append({
                "rank": idx,
                "user_id": row.user_id,
                "telegram_id": row.telegram_id,
                "username": row.username,
                "referral_count": row.referral_count,
                "total_earnings": Decimal(str(row.total_earnings)),
            })

        return {
            "by_referrals": by_referrals,
            "by_earnings": by_earnings,
        }

    async def get_user_leaderboard_position(self, user_id: int) -> dict:
        """
        Get user's position in leaderboard.

        Args:
            user_id: User ID

        Returns:
            Dict with referral_rank, earnings_rank, total_users
        """
        # Get all users with referrals
        stmt = text("""
            WITH referral_stats AS (
                SELECT
                    r.referrer_id,
                    COUNT(DISTINCT r.referral_id) as referral_count,
                    COALESCE(SUM(re.amount), 0) as total_earnings
                FROM referrals r
                LEFT JOIN referral_earnings re ON re.referral_id = r.id
                GROUP BY r.referrer_id
            )
            SELECT
                referrer_id,
                referral_count,
                total_earnings,
                RANK() OVER (ORDER BY referral_count DESC,
                             total_earnings DESC) as referral_rank,
                RANK() OVER (ORDER BY total_earnings DESC,
                             referral_count DESC) as earnings_rank
            FROM referral_stats
        """)

        result = await self.session.execute(stmt)
        rows = result.fetchall()

        # Find user's position
        referral_rank = None
        earnings_rank = None

        for row in rows:
            if row.referrer_id == user_id:
                referral_rank = row.referral_rank
                earnings_rank = row.earnings_rank
                break

        return {
            "referral_rank": referral_rank,
            "earnings_rank": earnings_rank,
            "total_users": len(rows),
        }

    async def get_platform_referral_stats(self) -> dict:
        """
        Get platform-wide referral statistics.

        Returns:
            Dict with total referrals, earnings breakdown
        """
        # Get all referrals
        all_referrals = await self.referral_repo.find_by()

        # Count by level
        by_level = {}
        for level in [1, 2, 3]:
            level_refs = [r for r in all_referrals if r.level == level]
            level_earnings = sum(r.total_earned for r in level_refs)
            by_level[level] = {
                "count": len(level_refs),
                "earnings": level_earnings,
            }

        # Get all earnings
        all_earnings = await self.earning_repo.find_by()
        total_earnings = sum(e.amount for e in all_earnings)
        paid_earnings = sum(e.amount for e in all_earnings if e.paid)
        pending_earnings = sum(e.amount for e in all_earnings if not e.paid)

        return {
            "total_referrals": len(all_referrals),
            "total_earnings": total_earnings,
            "paid_earnings": paid_earnings,
            "pending_earnings": pending_earnings,
            "by_level": by_level,
        }
