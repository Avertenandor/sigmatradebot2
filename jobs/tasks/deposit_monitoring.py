"""
Deposit monitoring task.

Monitors blockchain for deposit confirmations and updates deposit status.
Runs every minute to check pending deposits.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import dramatiq
from aiogram import Bot
from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.config.settings import settings
from app.models.enums import TransactionStatus
from app.repositories.deposit_repository import DepositRepository
from app.services.blockchain_service import get_blockchain_service
from app.services.deposit_service import DepositService
from app.services.notification_service import NotificationService


@dramatiq.actor(max_retries=3, time_limit=300_000)  # 5 min timeout
def monitor_deposits() -> None:
    """
    Monitor pending deposits for blockchain confirmations.

    Checks all pending deposits against blockchain, confirms deposits
    with sufficient confirmations (e.g., 12 blocks on BSC).
    """
    logger.info("Starting deposit monitoring...")

    try:
        # Run async code
        asyncio.run(_monitor_deposits_async())
        logger.info("Deposit monitoring complete")

    except Exception as e:
        logger.exception(f"Deposit monitoring failed: {e}")


async def _monitor_deposits_async() -> None:
    """Async implementation of deposit monitoring."""
    # Create local engine
    local_engine = create_async_engine(
        settings.database_url,
        echo=False,
        poolclass=NullPool,
    )
    
    local_session_maker = async_sessionmaker(
        local_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    try:
        async with local_session_maker() as session:
            deposit_repo = DepositRepository(session)
            deposit_service = DepositService(session)
            blockchain_service = get_blockchain_service()

            # Initialize bot for notifications (used for both recovery and regular processing)
            bot = Bot(token=settings.telegram_bot_token)
            notification_service = NotificationService(session)

            # R11-2: Batch process deposits with PENDING_NETWORK_RECOVERY status
            # when blockchain network is recovered
            recovery_confirmed = 0
            recovery_still_pending = 0
            
            if not settings.blockchain_maintenance_mode:
                from sqlalchemy import select
                from sqlalchemy.orm import selectinload
                from app.models.deposit import Deposit as DepositModel

                # Find all deposits waiting for network recovery
                recovery_stmt = (
                    select(DepositModel)
                    .options(selectinload(DepositModel.user))
                    .where(
                        DepositModel.status
                        == TransactionStatus.PENDING_NETWORK_RECOVERY.value
                    )
                )
                recovery_result = await session.execute(recovery_stmt)
                recovery_deposits = list(recovery_result.scalars().unique().all())

                if recovery_deposits:
                    logger.info(
                        f"R11-2: Processing {len(recovery_deposits)} deposits "
                        "waiting for network recovery"
                    )

                    for deposit in recovery_deposits:
                        try:
                            if deposit.user and deposit.user.wallet_address:
                                # Search blockchain for the deposit
                                found_tx = None
                                try:
                                    found_tx = (
                                        await blockchain_service.search_blockchain_for_deposit(
                                            user_wallet=deposit.user.wallet_address,
                                            expected_amount=deposit.amount,
                                            from_block=0,
                                            to_block="latest",
                                            tolerance_percent=0.05,
                                        )
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"R11-2: Error searching blockchain for "
                                        f"recovery deposit {deposit.id}: {e}",
                                        extra={"deposit_id": deposit.id},
                                    )

                                if found_tx:
                                    # Found transaction - confirm deposit
                                    logger.info(
                                        f"R11-2: Found recovery deposit {deposit.id} "
                                        f"in blockchain: tx_hash={found_tx['tx_hash']}"
                                    )

                                    # Update deposit with transaction hash
                                    await deposit_repo.update(
                                        deposit.id, tx_hash=found_tx["tx_hash"]
                                    )

                                    # Confirm deposit
                                    await deposit_service.confirm_deposit(
                                        deposit.id, found_tx["block_number"]
                                    )
                                    recovery_confirmed += 1

                                    # Notify user
                                    if deposit.user:
                                        notification_message = (
                                            f"✅ Депозит подтверждён после восстановления сети!\n\n"
                                            f"Ваш депозит уровня {deposit.level} "
                                            f"({deposit.amount} USDT) был найден в блокчейне "
                                            f"и подтверждён.\n\n"
                                            f"Транзакция: {found_tx['tx_hash']}"
                                        )
                                        await notification_service.send_notification(
                                            bot,
                                            deposit.user.telegram_id,
                                            notification_message,
                                            critical=True,
                                        )
                                else:
                                    # Not found - keep as PENDING with new timeout
                                    await deposit_repo.update(
                                        deposit.id,
                                        status=TransactionStatus.PENDING.value,
                                    )
                                    recovery_still_pending += 1
                                    logger.info(
                                        f"R11-2: Recovery deposit {deposit.id} not found, "
                                        "converted to PENDING status"
                                    )

                        except Exception as e:
                            logger.error(
                                f"R11-2: Error processing recovery deposit {deposit.id}: {e}",
                                extra={"deposit_id": deposit.id},
                                exc_info=True,
                            )

                    if recovery_confirmed > 0 or recovery_still_pending > 0:
                        await session.commit()
                        logger.info(
                            f"R11-2: Recovery processing complete: "
                            f"{recovery_confirmed} confirmed, "
                            f"{recovery_still_pending} converted to PENDING"
                        )

            # Get pending deposits with user relationship loaded
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            from app.models.deposit import Deposit as DepositModel

            stmt = (
                select(DepositModel)
                .options(selectinload(DepositModel.user))
                .where(DepositModel.status == TransactionStatus.PENDING.value)
            )
            result = await session.execute(stmt)
            pending_deposits = list(result.scalars().unique().all())

            # Filter deposits with tx_hash
            pending_with_tx = [d for d in pending_deposits if d.tx_hash]

            # R3-6: Check for expired deposits (24 hours without tx_hash)
            expired_count = 0
            timeout_threshold = datetime.now(UTC) - timedelta(hours=24)
            pending_without_tx = [
                d for d in pending_deposits
                if not d.tx_hash and d.created_at < timeout_threshold
            ]

            # Process expired deposits
            for deposit in pending_without_tx:
                try:
                    # R3-6: Last attempt to find transaction in blockchain history
                    # before marking as failed
                    found_tx = None
                    if deposit.user and deposit.user.wallet_address:
                        try:
                            # Estimate from_block: BSC has ~3 blocks/sec, ~10,800 blocks/hour
                            # Search from 24 hours ago (about 259,200 blocks)
                            # But limit to last 100k blocks to avoid excessive RPC calls
                            from_block = 0  # Search from beginning (limited by service)
                            
                            found_tx = await blockchain_service.search_blockchain_for_deposit(
                                user_wallet=deposit.user.wallet_address,
                                expected_amount=deposit.amount,
                                from_block=from_block,
                                to_block="latest",
                                tolerance_percent=0.05,  # 5% tolerance
                            )
                        except Exception as e:
                            logger.warning(
                                f"Error searching blockchain for deposit {deposit.id}: {e}",
                                extra={"deposit_id": deposit.id},
                            )

                    if found_tx:
                        # Found transaction - confirm deposit
                        logger.info(
                            f"Found expired deposit {deposit.id} in blockchain: "
                            f"tx_hash={found_tx['tx_hash']}, "
                            f"block={found_tx['block_number']}"
                        )
                        
                        # Update deposit with transaction hash first
                        await deposit_repo.update(
                            deposit.id,
                            tx_hash=found_tx["tx_hash"],
                        )
                        
                        # Confirm deposit through service (handles status, balance updates, referrals)
                        await deposit_service.confirm_deposit(
                            deposit.id, found_tx["block_number"]
                        )
                        
                        # Notify user of successful confirmation
                        if deposit.user:
                            notification_message = (
                                f"✅ Депозит подтверждён!\n\n"
                                f"Ваш депозит уровня {deposit.level} "
                                f"({deposit.amount} USDT) был найден в блокчейне и подтверждён.\n\n"
                                f"Транзакция: {found_tx['tx_hash']}"
                            )
                            await notification_service.send_notification(
                                bot,
                                deposit.user.telegram_id,
                                notification_message,
                                critical=True,
                            )
                        continue

                    # Transaction not found - mark as failed
                    await deposit_repo.update(
                        deposit.id, status=TransactionStatus.FAILED.value
                    )
                    expired_count += 1

                    logger.warning(
                        f"Deposit {deposit.id} expired (24h timeout, not found in blockchain)",
                        extra={
                            "deposit_id": deposit.id,
                            "user_id": deposit.user_id,
                            "level": deposit.level,
                            "amount": str(deposit.amount),
                            "created_at": deposit.created_at.isoformat(),
                        },
                    )

                    # R3-6: Notify user (user already loaded via selectinload)
                    if deposit.user:
                        notification_message = (
                            f"⚠️ Депозит не был подтверждён в течение 24 часов.\n\n"
                            f"Ваш запрос на депозит уровня {deposit.level} "
                            f"({deposit.amount} USDT) создан более 24 часов назад.\n\n"
                            f"Транзакция не была найдена в блокчейне.\n\n"
                            f"Если вы уже отправили средства, свяжитесь с поддержкой.\n\n"
                            f"Если средства НЕ были отправлены, вы можете создать новый депозит."
                        )
                        await notification_service.send_notification(
                            bot,
                            deposit.user.telegram_id,
                            notification_message,
                            critical=False,
                        )

                except Exception as e:
                    logger.error(
                        f"Error processing expired deposit {deposit.id}: {e}",
                        extra={"deposit_id": deposit.id},
                        exc_info=True,
                    )

            if not pending_with_tx:
                logger.debug("No pending deposits with tx_hash found")
                await session.commit()
                await bot.session.close()
                return

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
                        block_number = tx_status.get("block_number", 0)
                        await deposit_service.confirm_deposit(
                            deposit.id, block_number
                        )
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
            await bot.session.close()

            # R11-2: Include recovery processing results
            logger.info(
                f"Deposit monitoring stats: "
                f"{processed} processed, {confirmed} confirmed, "
                f"{still_pending} still pending, {expired_count} expired"
            )

    finally:
        await local_engine.dispose()
