"""
Node Health Monitor (R7-5).

Monitors blockchain node health and activates maintenance mode if needed.
Runs every 30 seconds.
"""

import asyncio

import dramatiq
from aiogram import Bot
from loguru import logger

from app.config.database import async_session_maker
from app.config.settings import settings
from app.services.blockchain_service import get_blockchain_service
from app.services.notification_service import NotificationService


@dramatiq.actor(max_retries=3, time_limit=60_000)  # 1 min timeout
def monitor_node_health() -> None:
    """
    Monitor blockchain node health (R7-5).

    Checks node availability every 30 seconds.
    If all nodes fail, activates maintenance mode and notifies admins.
    """
    logger.debug("Starting node health check...")

    try:
        asyncio.run(_monitor_node_health_async())
    except Exception as e:
        logger.exception(f"Node health monitoring failed: {e}")


async def _monitor_node_health_async() -> None:
    """Async implementation of node health monitoring."""
    blockchain_service = get_blockchain_service()

    try:
        # Check provider health
        status = await blockchain_service.get_providers_status()

        # Check if ANY provider is connected
        is_healthy = any(p.get("connected", False) for p in status.values())

        # If healthy, we're good
        if is_healthy:
            # If maintenance mode was active, deactivate it
            if settings.blockchain_maintenance_mode:
                settings.blockchain_maintenance_mode = False
                logger.info("Blockchain maintenance mode deactivated")
            return

        # HTTP is down - activate maintenance mode
        logger.warning("Blockchain node health check failed (HTTP down)")

        if not settings.blockchain_maintenance_mode:
            settings.blockchain_maintenance_mode = True
            logger.critical(
                "Blockchain node unavailable. "
                "Maintenance mode activated."
            )
            # Notify admins
            await _notify_admins_maintenance_mode()

    except Exception as e:
        logger.error(f"Error during node health check: {e}")

        # Activate maintenance mode on error
        if not settings.blockchain_maintenance_mode:
            settings.blockchain_maintenance_mode = True
            logger.critical(
                "Error checking node health. Maintenance mode activated."
            )
        return


async def _notify_admins_maintenance_mode() -> None:
    """Notify admins about maintenance mode activation."""
    try:
        async with async_session_maker() as session:
            bot = Bot(token=settings.telegram_bot_token)
            notification_service = NotificationService(session)

            admin_ids = settings.get_admin_ids()

            message = (
                "🚨 **КРИТИЧНО: Blockchain Maintenance Mode активирован**\n\n"
                "Все blockchain узлы недоступны.\n"
                "Операции с блокчейном временно приостановлены.\n\n"
                "Требуется немедленное вмешательство администратора."
            )

            for admin_id in admin_ids:
                await notification_service.send_notification(
                    bot, admin_id, message, critical=True
                )

            await bot.session.close()

    except Exception as e:
        logger.error(f"Error notifying admins: {e}")



