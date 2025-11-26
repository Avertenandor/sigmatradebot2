import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.config.settings import settings
from app.models.user import User
from app.models.deposit import Deposit, DepositStatus
from app.models.deposit_reward import DepositReward

async def audit_deposits():
    logger.info("🚀 Starting deposit audit...")

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
            # 1. Get all confirmed deposits
            stmt = (
                select(Deposit)
                .options(selectinload(Deposit.user), selectinload(Deposit.rewards))
                .where(Deposit.status == DepositStatus.CONFIRMED)
                .order_by(Deposit.created_at)
            )
            result = await session.execute(stmt)
            deposits = result.scalars().all()

            logger.info(f"Found {len(deposits)} CONFIRMED deposits.")

            for deposit in deposits:
                user = deposit.user
                rewards = deposit.rewards
                total_rewards = sum(r.amount for r in rewards)
                last_reward = rewards[-1] if rewards else None
                
                logger.info(f"--- Deposit ID: {deposit.id} ---")
                logger.info(f"User: {user.id} (@{user.username or 'NoUsername'})")
                logger.info(f"Amount: {deposit.amount} USDT")
                logger.info(f"Level: {deposit.level}")
                logger.info(f"Created At: {deposit.created_at}")
                logger.info(f"Next Accrual At: {deposit.next_accrual_at}")
                logger.info(f"ROI Paid: {deposit.roi_paid_amount} (Calc from rewards: {total_rewards})")
                logger.info(f"ROI Cap: {deposit.roi_cap_amount}")
                logger.info(f"Is Completed: {deposit.is_roi_completed}")
                
                if last_reward:
                    logger.info(f"Last Reward: {last_reward.amount} at {last_reward.created_at}")
                else:
                    logger.info("No rewards yet.")

                # Check for issues
                now = datetime.now(deposit.created_at.tzinfo)
                if deposit.next_accrual_at and deposit.next_accrual_at < now:
                    logger.warning(f"⚠️ ALERT: Next accrual was due at {deposit.next_accrual_at} (Past due!)")
                
                if deposit.roi_paid_amount >= deposit.roi_cap_amount and not deposit.is_roi_completed:
                     logger.warning(f"⚠️ ALERT: ROI Cap reached but not marked completed!")

    except Exception as e:
        logger.exception(f"Audit failed: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(audit_deposits())

