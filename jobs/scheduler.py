"""
Task scheduler.

APScheduler-based periodic task scheduling for background jobs.
"""

import sys
import warnings
from pathlib import Path

# Suppress eth_utils network warnings about invalid ChainId
# These warnings are from eth_utils library initialization and don't affect functionality
# Must be set BEFORE importing any modules that use eth_utils
warnings.filterwarnings(
    "ignore",
    message=".*does not have a valid ChainId.*",
    category=UserWarning,
    module="eth_utils.network",
)
# Also suppress warnings from any module that may import eth_utils
warnings.filterwarnings(
    "ignore",
    message=".*does not have a valid ChainId.*",
    category=UserWarning,
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Initialize blockchain service for scheduler tasks
from app.config.settings import settings
from app.services.blockchain_service import init_blockchain_service

try:
    init_blockchain_service(
        rpc_url=settings.rpc_url,
        usdt_contract=settings.usdt_contract_address,
        wallet_private_key=settings.wallet_private_key,
    )
    logger.info("BlockchainService initialized for scheduler")
except Exception as e:
    logger.error(f"Failed to initialize BlockchainService: {e}")
    logger.warning(
        "Scheduler will continue, but blockchain operations may fail"
    )

from jobs.tasks.admin_session_cleanup import (
    cleanup_expired_admin_sessions,
)
from jobs.tasks.daily_rewards import process_daily_rewards
from jobs.tasks.deposit_monitoring import monitor_deposits
from jobs.tasks.notification_retry import process_notification_retries
from jobs.tasks.payment_retry import process_payment_retries


def create_scheduler() -> AsyncIOScheduler:
    """
    Create and configure task scheduler.

    Returns:
        Configured AsyncIOScheduler instance
    """
    scheduler = AsyncIOScheduler()

    # PART5 Critical: Payment retry - every 1 minute
    scheduler.add_job(
        process_payment_retries.send,
        trigger=IntervalTrigger(minutes=1),
        id="payment_retry",
        name="Payment Retry Processing",
        replace_existing=True,
    )

    # PART5 Critical: Notification retry - every 1 minute
    scheduler.add_job(
        process_notification_retries.send,
        trigger=IntervalTrigger(minutes=1),
        id="notification_retry",
        name="Notification Retry Processing",
        replace_existing=True,
    )

    # Deposit monitoring - every 1 minute
    scheduler.add_job(
        monitor_deposits.send,
        trigger=IntervalTrigger(minutes=1),
        id="deposit_monitoring",
        name="Deposit Monitoring",
        replace_existing=True,
    )

    # Daily rewards - every day at 00:00 UTC
    scheduler.add_job(
        process_daily_rewards.send,
        trigger=CronTrigger(hour=0, minute=0),
        id="daily_rewards",
        name="Daily Rewards Processing",
        replace_existing=True,
    )

    # Admin session cleanup - every 5 minutes
    scheduler.add_job(
        cleanup_expired_admin_sessions.send,
        trigger=IntervalTrigger(minutes=5),
        id="admin_session_cleanup",
        name="Admin Session Cleanup",
        replace_existing=True,
    )

    logger.info("Task scheduler configured with 5 jobs")

    return scheduler


async def start_scheduler() -> None:
    """Start the task scheduler."""
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Task scheduler started")


if __name__ == "__main__":
    import asyncio

    async def main():
        await start_scheduler()
        # Keep running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped")

    asyncio.run(main())
