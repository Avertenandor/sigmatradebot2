"""
Payment retry task (PART5 critical).

Processes pending payment retries with exponential backoff.
Runs every minute to check for retries ready for processing.
"""

import asyncio

import dramatiq
from loguru import logger

from app.config.database import async_session_maker
from app.services.blockchain_service import get_blockchain_service
from app.services.payment_retry_service import PaymentRetryService


@dramatiq.actor(max_retries=3, time_limit=300_000)  # 5 min timeout
def process_payment_retries() -> dict:
    """
    Process pending payment retries.

    PART5 critical: Ensures failed payments are retried with exponential
    backoff (1min, 2min, 4min, 8min, 16min) and moved to DLQ after 5
    attempts.

    Returns:
        Dict with processed, successful, failed, moved_to_dlq counts
    """
    logger.info("Starting payment retry processing...")

    try:
        # Run async code
        result = asyncio.run(_process_payment_retries_async())

        logger.info(
            f"Payment retry processing complete: "
            f"{result['successful']} successful, "
            f"{result['failed']} failed, "
            f"{result['moved_to_dlq']} moved to DLQ"
        )

        return result

    except Exception as e:
        logger.exception(f"Payment retry processing failed: {e}")
        return {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "moved_to_dlq": 0,
            "error": str(e),
        }


async def _process_payment_retries_async() -> dict:
    """Async implementation of payment retry processing."""
    async with async_session_maker() as session:
        # Get blockchain service
        blockchain_service = get_blockchain_service()

        # Process retries
        retry_service = PaymentRetryService(session)
        result = await retry_service.process_pending_retries(
            blockchain_service
        )

        return result
