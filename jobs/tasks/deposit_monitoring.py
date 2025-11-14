"""
Deposit monitoring task.

Monitors blockchain for deposit confirmations and updates deposit status.
Runs every minute to check pending deposits.
"""

import asyncio

import dramatiq
from loguru import logger

from app.config.database import async_session_maker
from app.models.enums import TransactionStatus
from app.repositories.deposit_repository import DepositRepository
from app.services.blockchain_service import get_blockchain_service
from app.services.deposit_service import DepositService


@dramatiq.actor(max_retries=3, time_limit=300_000)  # 5 min timeout
def monitor_deposits() -> dict:
    """
    Monitor pending deposits for blockchain confirmations.

    Checks all pending deposits against blockchain, confirms deposits
    with sufficient confirmations (e.g., 12 blocks on BSC).

    Returns:
        Dict with processed, confirmed, still_pending counts
    """
    logger.info("Starting deposit monitoring...")

    try:
        # Run async code
        result = asyncio.run(_monitor_deposits_async())

        logger.info(
            f"Deposit monitoring complete: "
            f"{result['confirmed']} confirmed, "
            f"{result['still_pending']} still pending"
        )

        return result

    except Exception as e:
        logger.exception(f"Deposit monitoring failed: {e}")
        return {
            "processed": 0,
            "confirmed": 0,
            "still_pending": 0,
            "error": str(e),
        }


async def _monitor_deposits_async() -> dict:
    """Async implementation of deposit monitoring."""
    async with async_session_maker() as session:
        deposit_repo = DepositRepository(session)
        deposit_service = DepositService(session)
        blockchain_service = get_blockchain_service()

        # Get pending deposits with tx_hash
        pending_deposits = await deposit_repo.find_by(
            status=TransactionStatus.PENDING.value
        )

        # Filter deposits with tx_hash
        pending_with_tx = [
            d for d in pending_deposits if d.tx_hash
        ]

        if not pending_with_tx:
            logger.debug("No pending deposits with tx_hash found")
            return {
                "processed": 0,
                "confirmed": 0,
                "still_pending": 0,
            }

        processed = 0
        confirmed = 0
        still_pending = 0

        for deposit in pending_with_tx:
            try:
                # Check transaction status on blockchain
                tx_status = await blockchain_service.check_transaction_status(
                    deposit.tx_hash
                )

                processed += 1

                # If confirmed with sufficient confirmations
                if (
                    tx_status.get("status") == "confirmed"
                    and tx_status.get("confirmations", 0) >= 12
                ):
                    # Confirm deposit
                    await deposit_service.confirm_deposit(deposit.id)
                    confirmed += 1

                    logger.info(
                        f"Deposit {deposit.id} confirmed",
                        extra={
                            "deposit_id": deposit.id,
                            "tx_hash": deposit.tx_hash,
                            "confirmations": tx_status.get("confirmations"),
                        },
                    )
                else:
                    still_pending += 1

            except Exception as e:
                logger.error(
                    f"Error checking deposit {deposit.id}: {e}",
                    extra={
                        "deposit_id": deposit.id,
                        "tx_hash": deposit.tx_hash,
                    },
                )

        await session.commit()

        return {
            "processed": processed,
            "confirmed": confirmed,
            "still_pending": still_pending,
        }
