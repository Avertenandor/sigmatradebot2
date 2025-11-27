#!/usr/bin/env python3
"""
Fix script to credit existing referral earnings to user balances.
Marks them as paid (internal_balance).
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import selectinload

from app.config.settings import settings
from app.models.referral_earning import ReferralEarning
from app.models.referral import Referral
from app.models.user import User

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")

async def fix_referral_balances():
    logger.info("🚀 Starting referral balance fix...")

    engine = create_async_engine(
        settings.database_url,
        echo=False,
        poolclass=NullPool,
    )
    
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    try:
        async with session_maker() as session:
            # Find unpaid earnings and eager load relationships
            stmt = (
                select(ReferralEarning)
                .where(ReferralEarning.paid == False)
                .options(
                    selectinload(ReferralEarning.referral).selectinload(Referral.referrer)
                )
            )
            result = await session.execute(stmt)
            earnings = result.scalars().all()

            if not earnings:
                logger.info("✅ No unpaid earnings found.")
                return

            logger.info(f"Found {len(earnings)} unpaid earnings to process.")

            processed_count = 0
            total_amount = 0

            for earning in earnings:
                if not earning.referral:
                    logger.warning(f"Earning {earning.id} has no referral relationship!")
                    continue
                
                referrer = earning.referral.referrer
                if not referrer:
                    logger.warning(f"Referral {earning.referral.id} has no referrer!")
                    continue

                # Credit balance
                amount = earning.amount
                referrer.balance += amount
                referrer.total_earned += amount
                
                # Mark as paid
                earning.paid = True
                earning.tx_hash = 'internal_balance'

                session.add(referrer)
                session.add(earning)
                
                processed_count += 1
                total_amount += amount

            await session.commit()
            logger.success(f"✅ Processed {processed_count} earnings.")
            logger.success(f"💰 Total credited: {total_amount} USDT")

    except Exception as e:
        logger.exception(f"Script error: {e}")
    finally:
        await engine.dispose()
        logger.info("🏁 Fix finished.")

if __name__ == "__main__":
    asyncio.run(fix_referral_balances())
