"""
Payment retry task (PART5 critical).

Processes pending payment retries with exponential backoff.
Runs every minute to check for retries ready for processing.
"""

import asyncio

import dramatiq
from loguru import logger

from app.services.blockchain_service import get_blockchain_service
from app.services.payment_retry_service import PaymentRetryService


@dramatiq.actor(max_retries=3, time_limit=300_000)  # 5 min timeout
def process_payment_retries() -> None:
    """
    Process pending payment retries.

    PART5 critical: Ensures failed payments are retried with exponential
    backoff (1min, 2min, 4min, 8min, 16min) and moved to DLQ after 5
    attempts.
    """
    logger.info("Starting payment retry processing...")

    try:
        asyncio.run(_process_payment_retries_async())
        logger.info("Payment retry processing complete")

    except Exception as e:
        logger.exception(f"Payment retry processing failed: {e}")


async def _process_payment_retries_async() -> None:
    """Async implementation of payment retry processing."""
    # Create a dedicated engine and sessionmaker for this run to avoid cross-loop reuse
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from app.config.settings import settings
    
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        poolclass=NullPool,
    )
    SessionLocal = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
    
    try:
        async with SessionLocal() as session:
            # Get blockchain service
            blockchain_service = get_blockchain_service()

            # Process retries
            retry_service = PaymentRetryService(session)
            await retry_service.process_pending_retries(
                blockchain_service
            )

    finally:
        await engine.dispose()
