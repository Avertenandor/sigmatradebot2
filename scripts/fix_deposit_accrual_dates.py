import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.config.settings import settings
from app.models.deposit import Deposit
from app.models.enums import TransactionStatus
from app.models.global_settings import GlobalSettings
from app.repositories.global_settings_repository import GlobalSettingsRepository

async def fix_deposit_accrual_dates():
    """
    Fix missing next_accrual_at dates for confirmed deposits.
    Sets next_accrual_at to now() to trigger immediate processing by the scheduler.
    """
    logger.info("🚀 Starting deposit accrual date fix...")

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
            # 1. Get Global Settings for accrual period
            settings_repo = GlobalSettingsRepository(session)
            global_settings = await settings_repo.get_settings()
            
            roi_settings = global_settings.roi_settings or {}
            accrual_period_hours = int(roi_settings.get("accrual_period_hours", 24))
            
            logger.info(f"Global Accrual Period: {accrual_period_hours} hours")

            # 2. Find confirmed deposits with missing next_accrual_at
            stmt = (
                select(Deposit)
                .where(
                    Deposit.status == TransactionStatus.CONFIRMED.value,
                    Deposit.next_accrual_at.is_(None),
                    Deposit.is_roi_completed == False
                )
            )
            result = await session.execute(stmt)
            deposits = result.scalars().all()

            if not deposits:
                logger.info("✅ No deposits found needing fix.")
                return

            logger.info(f"Found {len(deposits)} deposits to fix.")

            now = datetime.now(timezone.utc)
            
            # Set to NOW to ensure they get picked up immediately by the next run of reward_accrual_task
            # Alternatively, we could set it to confirmed_at + period, but if that was days ago, 
            # we might want to process them now anyway.
            # The task processes "deposits where next_accrual_at <= now".
            
            for deposit in deposits:
                logger.info(f"Fixing Deposit {deposit.id} (Confirmed at: {deposit.confirmed_at})")
                
                # Set next accrual to NOW so the scheduler picks it up immediately
                deposit.next_accrual_at = now
                
                # Note: We don't calculate backpay here. The regular task will run once. 
                # If multiple periods were missed, the regular task logic (if robust) might handle it, 
                # or it will just start from now. Given "emergency fix", starting from now is safest 
                # to verify the system works.
                
                session.add(deposit)
            
            await session.commit()
            logger.success(f"✅ Successfully fixed {len(deposits)} deposits.")

    except Exception as e:
        logger.exception(f"Fix script failed: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_deposit_accrual_dates())

