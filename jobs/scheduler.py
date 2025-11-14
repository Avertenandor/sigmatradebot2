"""
Task scheduler.

APScheduler-based periodic task scheduling for background jobs.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

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

    logger.info("Task scheduler configured with 4 jobs")

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
