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
from app.config.database import async_session_maker
from app.config.settings import settings
from app.services.blockchain_service import init_blockchain_service

try:
    init_blockchain_service(
        settings=settings,
        session_factory=async_session_maker,
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
from jobs.tasks.financial_reconciliation import (
    perform_financial_reconciliation,
)
from jobs.tasks.metrics_monitor import monitor_metrics
from jobs.tasks.node_health_monitor import monitor_node_health
from jobs.tasks.notification_retry import process_notification_retries
from jobs.tasks.payment_retry import process_payment_retries
from jobs.tasks.stuck_transaction_monitor import monitor_stuck_transactions
from jobs.tasks.mark_immutable_audit_logs import mark_immutable_audit_logs
from jobs.tasks.notification_fallback_processor import (
    process_notification_fallback,
)
from jobs.tasks.warmup_redis_cache import warmup_redis_cache
from jobs.tasks.incoming_transfer_monitor import monitor_incoming_transfers
from app.tasks.reward_accrual_task import run_individual_reward_accrual
from app.tasks.deposit_reminder_task import run_deposit_reminder_task
from app.tasks.cleanup_task import run_cleanup_task


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

    # R11-3: Notification fallback processor - every 5 seconds
    scheduler.add_job(
        process_notification_fallback.send,
        trigger=IntervalTrigger(seconds=5),
        id="notification_fallback",
        name="Notification Fallback Processing",
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

    # New: Incoming transfer monitor - every 1 minute
    scheduler.add_job(
        monitor_incoming_transfers.send,
        trigger=IntervalTrigger(minutes=1),
        id="incoming_transfer_monitor",
        name="Incoming Transfer Monitor",
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

    # R10-2: Financial reconciliation - every day at 01:00 UTC
    scheduler.add_job(
        perform_financial_reconciliation.send,
        trigger=CronTrigger(hour=1, minute=0),
        id="financial_reconciliation",
        name="Financial Reconciliation",
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

    # R7-6: Stuck transaction monitor - every 5 minutes
    scheduler.add_job(
        monitor_stuck_transactions.send,
        trigger=IntervalTrigger(minutes=5),
        id="stuck_transaction_monitor",
        name="Stuck Transaction Monitor",
        replace_existing=True,
    )

    # R7-5: Node health monitor - every 30 seconds
    scheduler.add_job(
        monitor_node_health.send,
        trigger=IntervalTrigger(seconds=30),
        id="node_health_monitor",
        name="Node Health Monitor",
        replace_existing=True,
    )

    # R14-1: Metrics monitor - every 5 minutes
    scheduler.add_job(
        monitor_metrics.send,
        trigger=IntervalTrigger(minutes=5),
        id="metrics_monitor",
        name="Metrics Monitor",
        replace_existing=True,
    )

    # R18-4: Mark immutable audit logs - daily at 02:00 UTC
    scheduler.add_job(
        mark_immutable_audit_logs.send,
        trigger=CronTrigger(hour=2, minute=0),
        id="mark_immutable_audit_logs",
        name="Mark Immutable Audit Logs",
        replace_existing=True,
    )

    # R11-3: Warmup Redis cache - every 1 minute (when Redis is healthy)
    scheduler.add_job(
        warmup_redis_cache.send,
        trigger=IntervalTrigger(minutes=1),
        id="warmup_redis_cache",
        name="Warmup Redis Cache",
        replace_existing=True,
    )

    # Individual reward accrual - every 5 minutes
    scheduler.add_job(
        run_individual_reward_accrual,
        trigger=IntervalTrigger(minutes=5),
        id="individual_reward_accrual",
        name="Individual Reward Accrual",
        replace_existing=True,
    )

    # Deposit reminder - every 6 hours
    scheduler.add_job(
        run_deposit_reminder_task,
        trigger=IntervalTrigger(hours=6),
        id="deposit_reminder",
        name="Deposit Reminder",
        replace_existing=True,
    )

    # Cleanup task - every week (Sunday at 04:00 UTC)
    scheduler.add_job(
        run_cleanup_task,
        trigger=CronTrigger(day_of_week="sun", hour=4, minute=0),
        id="cleanup_task",
        name="Data Cleanup Task",
        replace_existing=True,
    )

    logger.info("Task scheduler configured with 16 jobs")

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
