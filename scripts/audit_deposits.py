import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from enum import Enum

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.config.settings import settings
from app.models.user import User
from app.models.deposit import Deposit
from app.models.deposit_reward import DepositReward

# Define Enum locally if not available in model
class DepositStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    ROI_COMPLETED = "roi_completed"
    PENDING_NETWORK_RECOVERY = "pending_network_recovery"

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
                .where(Deposit.status == DepositStatus.CONFIRMED.value)
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
                
                print(f"\n--- Deposit ID: {deposit.id} ---")
                print(f"User: {user.id} (ID: {user.telegram_id}, Username: @{user.username or 'NoUsername'})")
                print(f"Amount: {deposit.amount} USDT")
                print(f"Level: {deposit.level}")
                print(f"Created At: {deposit.created_at}")
                print(f"Next Accrual At: {deposit.next_accrual_at}")
                print(f"ROI Paid (DB): {deposit.roi_paid_amount}")
                print(f"ROI Paid (Calc): {total_rewards}")
                print(f"ROI Cap: {deposit.roi_cap_amount}")
                print(f"Is Completed: {deposit.is_roi_completed}")
                
                if last_reward:
                    print(f"Last Reward: {last_reward.amount} at {last_reward.created_at}")
                else:
                    print("No rewards yet.")

                # Check for issues
                if deposit.next_accrual_at:
                    # Handle timezone awareness
                    now = datetime.now(deposit.next_accrual_at.tzinfo)
                    if deposit.next_accrual_at < now:
                        print(f"⚠️ ALERT: Next accrual was due at {deposit.next_accrual_at} (Past due!)")
                
                if deposit.roi_paid_amount >= deposit.roi_cap_amount and not deposit.is_roi_completed:
                     print(f"⚠️ ALERT: ROI Cap reached but not marked completed!")

    except Exception as e:
        logger.exception(f"Audit failed: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(audit_deposits())
