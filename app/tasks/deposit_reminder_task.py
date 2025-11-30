"""
Deposit reminder task.

Sends reminders to users who started but didn't complete deposits.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from loguru import logger

from app.config.database import async_session_maker


async def run_deposit_reminder_task() -> None:
    """
    Send reminders about incomplete deposits.

    This task:
    1. Finds users who started deposit flow but didn't complete
    2. Sends reminder after 24 hours
    3. Sends final reminder after 48 hours
    """
    logger.info("Starting deposit reminder task")

    try:
        async with async_session_maker() as session:
            try:
                from sqlalchemy import select, and_
                from app.models.deposit import Deposit
                from app.models.user import User
                from app.models.enums import DepositStatus
                from app.services.notification_service import NotificationService

                notification_service = NotificationService(session)

                # Find pending deposits older than 24 hours
                cutoff_24h = datetime.now(UTC) - timedelta(hours=24)
                cutoff_48h = datetime.now(UTC) - timedelta(hours=48)

                # Get deposits that are PENDING (user selected level but didn't pay)
                stmt = (
                    select(Deposit)
                    .join(User)
                    .where(
                        and_(
                            Deposit.status == DepositStatus.PENDING.value,
                            Deposit.created_at <= cutoff_24h,
                            Deposit.created_at > cutoff_48h,
                        )
                    )
                )
                result = await session.execute(stmt)
                pending_deposits = result.scalars().all()

                reminders_sent = 0
                for deposit in pending_deposits:
                    user = deposit.user
                    if not user or not user.telegram_id:
                        continue

                    try:
                        from bot.main import bot_instance

                        message = (
                            f"⏰ *Напоминание о депозите*\n\n"
                            f"Вы начали оформление депозита Level {deposit.level} "
                            f"({deposit.amount} USDT), но не завершили.\n\n"
                            f"Хотите продолжить? Перейдите в раздел '💰 Депозит'."
                        )

                        await bot_instance.send_message(
                            chat_id=user.telegram_id,
                            text=message,
                            parse_mode="Markdown",
                        )
                        reminders_sent += 1
                        logger.info(
                            f"Deposit reminder sent to user {user.id} "
                            f"for deposit {deposit.id}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to send deposit reminder: {e}",
                            extra={"user_id": user.id, "deposit_id": deposit.id},
                        )

                logger.info(
                    f"Deposit reminder task completed: {reminders_sent} reminders sent"
                )

            except Exception as e:
                logger.error(
                    f"Error in deposit reminder task: {e}",
                    extra={"error": str(e)},
                )
                raise

    except Exception as e:
        logger.error(
            f"Fatal error in deposit reminder task: {e}",
            extra={"error": str(e)},
        )

