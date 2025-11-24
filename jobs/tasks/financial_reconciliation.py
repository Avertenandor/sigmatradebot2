"""
Financial Reconciliation Task (R10-2).

Performs daily financial reconciliation to verify system balance integrity.
Runs daily at 01:00 UTC.
"""

import asyncio
from datetime import UTC, datetime

import dramatiq
from aiogram import Bot
from loguru import logger

from app.config.database import async_session_maker
from app.config.settings import settings
from app.services.notification_service import NotificationService
from app.services.reconciliation_service import ReconciliationService


@dramatiq.actor(max_retries=3, time_limit=600_000)  # 10 min timeout
def perform_financial_reconciliation() -> None:
    """
    Perform daily financial reconciliation.

    R10-2: Verifies system balance integrity by comparing:
    - Expected: SUM(confirmed_deposits) - SUM(confirmed_withdrawals)
                - SUM(paid_referral_earnings)
    - Actual: SUM(users.balance) + SUM(users.pending_earnings)
              + SUM(pending_withdrawals.amount)

    Uses 5% tolerance to account for commission fluctuations.
    """
    logger.info("Starting financial reconciliation...")

    try:
        # Run async code
        result = asyncio.run(_perform_reconciliation_async())

        if result.get("success"):
            if result.get("critical"):
                logger.error(
                    f"CRITICAL: Reconciliation discrepancy: "
                    f"{result.get('discrepancy_percent', 0):.2f}%"
                )
            else:
                logger.info(
                    f"Reconciliation complete: "
                    f"discrepancy={result.get('discrepancy', 0):.2f} USDT "
                    f"({result.get('discrepancy_percent', 0):.2f}%)"
                )

    except Exception as e:
        logger.exception(f"Financial reconciliation failed: {e}")


async def _perform_reconciliation_async() -> dict:
    """Async implementation of financial reconciliation."""
    async with async_session_maker() as session:
        reconciliation_service = ReconciliationService(session)

        # Perform reconciliation
        result = await reconciliation_service.perform_reconciliation()

        # If critical discrepancy, notify admins
        if result.get("critical"):
            try:
                # Initialize bot for notifications
                bot = Bot(token=settings.telegram_bot_token)
                notification_service = NotificationService(session)

                # Get admin telegram IDs (would need admin service)
                # For now, just log it
                logger.critical(
                    "CRITICAL RECONCILIATION DISCREPANCY DETECTED",
                    extra={
                        "snapshot_id": result.get("snapshot_id"),
                        "expected": result.get("expected_balance"),
                        "actual": result.get("actual_balance"),
                        "discrepancy": result.get("discrepancy"),
                        "discrepancy_percent": result.get(
                            "discrepancy_percent"
                        ),
                    },
                )

                # TODO: Send notification to all super_admins
                # This would require AdminService integration

                await bot.session.close()

            except Exception as e:
                logger.error(f"Error sending admin notification: {e}")

        return result



