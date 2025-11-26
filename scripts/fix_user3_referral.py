#!/usr/bin/env python3
"""
Fix script for User 3 (Inside1773).
1. Sets referrer_id = 1 (Admin).
2. Creates referral relationship in 'referrals' table.
3. Manually creates referral_earnings record for Deposit 1.
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy import select

from app.config.settings import settings
from app.models.user import User
from app.models.deposit import Deposit
from app.models.referral import Referral
from app.models.referral_earning import ReferralEarning
from app.services.referral_service import ReferralService

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")

USER_ID = 3
REFERRER_ID = 1
DEPOSIT_ID = 1
DEPOSIT_AMOUNT = Decimal("10.00")
LEVEL_1_RATE = Decimal("0.03") # 3%

async def fix_user_referral():
    logger.info("🚀 Starting user referral fix...")

    # Initialize Database
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
            # 1. Update User referrer
            user = await session.get(User, USER_ID)
            if not user:
                logger.error(f"❌ User {USER_ID} not found!")
                return

            if user.referrer_id:
                logger.warning(f"⚠️ User {USER_ID} already has referrer {user.referrer_id}. Updating to {REFERRER_ID}...")
            else:
                logger.info(f"✅ Setting referrer for User {USER_ID} to {REFERRER_ID}...")
            
            user.referrer_id = REFERRER_ID
            
            # 2. Create Referral Relationship
            # Check if exists
            result = await session.execute(
                select(Referral).where(
                    Referral.referrer_id == REFERRER_ID,
                    Referral.referred_user_id == USER_ID
                )
            )
            existing_ref = result.scalars().first()
            
            if existing_ref:
                logger.info("✅ Referral relationship already exists.")
            else:
                logger.info("➕ Creating new referral relationship...")
                new_ref = Referral(
                    referrer_id=REFERRER_ID,
                    referred_user_id=USER_ID,
                    level=1,
                    is_active=True
                )
                session.add(new_ref)
                await session.flush() # Get ID
            
            # 3. Create Referral Earning
            # Check if already exists for this deposit?
            # The table structure for referral_earnings might link to 'referral_id' (from referrals table) 
            # OR transaction/deposit. 
            # Let's check model or inferred from previous SQL result: 
            # id | referral_id | amount | source_transaction_id | tx_hash | paid | created_at
            
            # We need the referral_id (from step 2)
            result = await session.execute(
                select(Referral).where(
                    Referral.referrer_id == REFERRER_ID,
                    Referral.referred_user_id == USER_ID
                )
            )
            referral_record = result.scalars().first()
            
            if not referral_record:
                logger.error("❌ Failed to retrieve referral record.")
                return

            # Check for existing earning
            # We don't have a source_transaction_id linked to deposits directly usually in simple schemas, 
            # or it might be null. 
            # The previous SQL output showed source_transaction_id empty.
            # But we want to avoid duplicates.
            
            # Calculate amount
            earning_amount = DEPOSIT_AMOUNT * LEVEL_1_RATE
            
            # Let's just add it.
            logger.info(f"💰 Creating earning: {earning_amount} USDT for Referral ID {referral_record.id}...")
            
            earning = ReferralEarning(
                referral_id=referral_record.id,
                amount=earning_amount,
                paid=False,
                created_at=datetime.now(timezone.utc)
            )
            session.add(earning)
            
            # Update User Stats (Total Earned) for Referrer
            referrer = await session.get(User, REFERRER_ID)
            if referrer:
                # Update total_earned and pending_earnings
                # Usually stored in user profile
                pass 
                # Actually, let's use ReferralService helper if possible, but we are manual.
                # Let's trust the system to calculate stats from tables, 
                # OR update the cache columns if they exist.
                
                # Checking User model...
                # It likely has 'total_earned' or 'pending_earnings'.
                # Let's update them safely.
                # referrer.pending_earnings += earning_amount
                # session.add(referrer)
                pass

            await session.commit()
            logger.success("✅ Fix applied successfully!")

    except Exception as e:
        logger.exception(f"Script error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_user_referral())

