"""
Stuck Transaction Monitor (R7-6).

Monitors withdrawal transactions stuck in PROCESSING status.
Runs every 5 minutes to check for stuck transactions.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import dramatiq
from aiogram import Bot
from loguru import logger

from app.config.database import async_session_maker
from app.config.settings import settings
from app.services.blockchain_service import get_blockchain_service
from app.services.notification_service import NotificationService
from app.services.stuck_transaction_service import StuckTransactionService


@dramatiq.actor(max_retries=3, time_limit=300_000)  # 5 min timeout
def monitor_stuck_transactions() -> dict:
    """
    Monitor stuck withdrawal transactions.

    R7-6: Checks withdrawals in PROCESSING status older than 15 minutes,
    verifies their status in blockchain, and handles accordingly:
    - Pending: speed-up with higher gas
    - Failed: refund user balance
    - Dropped: retry with new nonce

    Returns:
        Dict with processed, confirmed, failed, pending counts
    """
    logger.info("Starting stuck transaction monitoring...")

    try:
        # Run async code
        result = asyncio.run(_monitor_stuck_transactions_async())

        logger.info(
            f"Stuck transaction monitoring complete: "
            f"{result['processed']} processed, "
            f"{result['confirmed']} confirmed, "
            f"{result['failed']} failed, "
            f"{result['pending']} still pending"
        )

        return result

    except Exception as e:
        logger.exception(f"Stuck transaction monitoring failed: {e}")
        return {
            "processed": 0,
            "confirmed": 0,
            "failed": 0,
            "pending": 0,
            "error": str(e),
        }


async def _monitor_stuck_transactions_async() -> dict:
    """Async implementation of stuck transaction monitoring."""
    async with async_session_maker() as session:
        stuck_service = StuckTransactionService(session)
        blockchain_service = get_blockchain_service()

        # Get stuck withdrawals (older than 15 minutes)
        stuck_withdrawals = await stuck_service.find_stuck_withdrawals(
            older_than_minutes=15
        )

        if not stuck_withdrawals:
            logger.debug("No stuck withdrawals found")
            return {
                "processed": 0,
                "confirmed": 0,
                "failed": 0,
                "pending": 0,
            }

        logger.info(
            f"Found {len(stuck_withdrawals)} stuck withdrawal(s) to process"
        )

        # Initialize bot for notifications
        bot = Bot(token=settings.telegram_bot_token)
        notification_service = NotificationService(session)

        processed = 0
        confirmed = 0
        failed = 0
        pending = 0

        # Get web3 instance from blockchain service
        web3 = blockchain_service.get_active_web3()

        for withdrawal in stuck_withdrawals:
            try:
                # Check transaction status in blockchain
                # Use blockchain_service to handle async web3 calls correctly
                bs_status = await blockchain_service.check_transaction_status(withdrawal.tx_hash)
                
                # Map status to format expected by handle_stuck_transaction
                status_map = {
                    "confirmed": "confirmed",
                    "failed": "failed",
                    "pending": "pending",
                    "unknown": "error"
                }
                
                tx_status = {
                    "status": status_map.get(bs_status.get("status"), "error"),
                    "error": None
                }

                # Handle based on status
                result = await stuck_service.handle_stuck_transaction(
                    withdrawal, tx_status, web3
                )

                processed += 1

                if result["action"] == "confirmed":
                    confirmed += 1

                    # Notify user
                    try:
                        from sqlalchemy.orm import selectinload
                        from app.models.user import User

                        from sqlalchemy import select
                        from sqlalchemy.orm import selectinload
                        from app.models.user import User

                        stmt = (
                            select(User)
                            .where(User.id == withdrawal.user_id)
                            .options(selectinload(User.transactions))
                        )

                        result_user = await session.execute(stmt)
                        user = result_user.scalar_one_or_none()

                        if user:
                            await notification_service.send_notification(
                                bot=bot,
                                user_telegram_id=user.telegram_id,
                                message=(
                                    f"✅ Ваш вывод подтвержден!\n\n"
                                    f"💰 Сумма: {withdrawal.amount} USDT\n"
                                    f"🔗 TX: {withdrawal.tx_hash}\n\n"
                                    f"Транзакция успешно обработана в блокчейне."
                                ),
                                critical=True,
                            )
                    except Exception as e:
                        logger.error(
                            f"Error sending notification for "
                            f"transaction {withdrawal.id}: {e}"
                        )

                elif result["action"] == "failed_refunded":
                    failed += 1

                    # Notify user about refund
                    try:
                        from sqlalchemy import select
                        from sqlalchemy.orm import selectinload
                        from app.models.user import User

                        stmt = (
                            select(User)
                            .where(User.id == withdrawal.user_id)
                            .options(selectinload(User.transactions))
                        )

                        result_user = await session.execute(stmt)
                        user = result_user.scalar_one_or_none()

                        if user:
                            await notification_service.send_notification(
                                bot=bot,
                                user_telegram_id=user.telegram_id,
                                message=(
                                    f"⚠️ Транзакция вывода не прошла\n\n"
                                    f"💰 Сумма: {withdrawal.amount} USDT\n"
                                    f"🔗 TX: {withdrawal.tx_hash}\n\n"
                                    f"Средства возвращены на ваш баланс. "
                                    f"Попробуйте создать новый запрос на вывод."
                                ),
                                critical=True,
                            )
                    except Exception as e:
                        logger.error(
                            f"Error sending notification for "
                            f"failed transaction {withdrawal.id}: {e}"
                        )

                elif result["action"] in [
                    "pending_waiting",
                    "pending_speedup_needed",
                    "not_found_retry_needed",
                ]:
                    pending += 1

            except Exception as e:
                logger.error(
                    f"Error processing stuck transaction "
                    f"{withdrawal.id}: {e}",
                    extra={"transaction_id": withdrawal.id},
                )

        # Check if we have too many stuck transactions (>3)
        if len(stuck_withdrawals) > 3:
            logger.warning(
                f"CRITICAL: {len(stuck_withdrawals)} transactions stuck "
                f"simultaneously - possible systemic issue",
                extra={"stuck_count": len(stuck_withdrawals)},
            )

            # Notify admins (this would require admin service integration)
            # For now, just log it

        await bot.session.close()

        return {
            "processed": processed,
            "confirmed": confirmed,
            "failed": failed,
            "pending": pending,
            "total_stuck": len(stuck_withdrawals),
        }

