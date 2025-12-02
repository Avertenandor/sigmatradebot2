"""
Fix Missing Referral Relationships.

This script creates missing records in 'referrals' table for users
who have referrer_id in 'users' table but no corresponding referral record.

Run: docker exec -it sigmatrade-bot python scripts/fix_missing_referrals.py
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import select, text

from app.config.database import async_session_maker
from app.models.referral import Referral
from app.models.user import User


REFERRAL_DEPTH = 3  # Max levels in referral chain


async def get_referral_chain(session, user_id: int, depth: int = REFERRAL_DEPTH) -> list[User]:
    """Get referral chain using recursive CTE."""
    query = text("""
        WITH RECURSIVE referral_chain AS (
            SELECT
                u.id,
                u.telegram_id,
                u.username,
                u.referrer_id,
                0 AS level
            FROM users u
            WHERE u.id = :user_id

            UNION ALL

            SELECT
                u.id,
                u.telegram_id,
                u.username,
                u.referrer_id,
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

    result = await session.execute(query, {"user_id": user_id, "depth": depth})
    rows = result.fetchall()
    return rows


async def fix_missing_referrals():
    """Fix missing referral records."""
    async with async_session_maker() as session:
        # Get all users with referrer_id
        stmt = select(User).where(User.referrer_id.isnot(None))
        result = await session.execute(stmt)
        users_with_referrer = list(result.scalars().all())
        
        logger.info(f"Found {len(users_with_referrer)} users with referrer_id")
        
        created_count = 0
        skipped_count = 0
        
        for user in users_with_referrer:
            # Check if referral record exists
            existing_stmt = select(Referral).where(
                Referral.referral_id == user.id,
                Referral.level == 1
            )
            existing_result = await session.execute(existing_stmt)
            existing = existing_result.scalar_one_or_none()
            
            if existing:
                logger.debug(f"User {user.id} already has referral record")
                skipped_count += 1
                continue
            
            # Get referral chain from direct referrer
            referrer_chain = await get_referral_chain(session, user.referrer_id, REFERRAL_DEPTH)
            
            # Create level 1 record for direct referrer
            direct_referral = Referral(
                referrer_id=user.referrer_id,
                referral_id=user.id,
                level=1,
                total_earned=Decimal("0"),
            )
            session.add(direct_referral)
            created_count += 1
            logger.info(
                f"Created referral: referrer={user.referrer_id} -> "
                f"referral={user.id} (level 1)"
            )
            
            # Create records for higher levels
            for row in referrer_chain:
                level = row.level + 1  # row.level is from CTE (0-based from direct referrer)
                if level > REFERRAL_DEPTH:
                    break
                
                # Check if already exists
                check_stmt = select(Referral).where(
                    Referral.referrer_id == row.id,
                    Referral.referral_id == user.id
                )
                check_result = await session.execute(check_stmt)
                if check_result.scalar_one_or_none():
                    continue
                
                higher_referral = Referral(
                    referrer_id=row.id,
                    referral_id=user.id,
                    level=level,
                    total_earned=Decimal("0"),
                )
                session.add(higher_referral)
                created_count += 1
                logger.info(
                    f"Created referral: referrer={row.id} -> "
                    f"referral={user.id} (level {level})"
                )
        
        await session.commit()
        
        logger.info(f"=== SUMMARY ===")
        logger.info(f"Created: {created_count} referral records")
        logger.info(f"Skipped: {skipped_count} (already existed)")
        
        # Verify
        verify_stmt = select(Referral)
        verify_result = await session.execute(verify_stmt)
        total_referrals = len(list(verify_result.scalars().all()))
        logger.info(f"Total referrals in DB: {total_referrals}")


if __name__ == "__main__":
    logger.add(sys.stderr, level="INFO")
    asyncio.run(fix_missing_referrals())

