#!/usr/bin/env python3
"""
Admin notification utility.

Sends Telegram notifications to all admins.
Used by backup scripts and maintenance procedures.

Usage:
    python scripts/notify_admin.py "Message text" [--critical]

Environment Variables:
    TELEGRAM_BOT_TOKEN: Telegram bot token (required)
    DATABASE_URL: PostgreSQL connection string (required)
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot  # noqa: E402
from loguru import logger  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.config.settings import settings  # noqa: E402
from app.services.notification_service import (  # noqa: E402
    NotificationService,
)


async def notify_admins(message: str, critical: bool = False) -> bool:
    """
    Send notification to all admins.

    Args:
        message: Message text to send
        critical: Mark as critical

    Returns:
        True if at least one admin was notified successfully
    """
    try:
        # Initialize bot
        bot = Bot(token=settings.telegram_bot_token)

        # Initialize database
        engine = create_async_engine(settings.database_url, echo=False)
        async_session_maker = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session_maker() as session:
            notification_service = NotificationService(session)
            success_count = await notification_service.notify_admins(
                bot, message, critical=critical
            )

            if success_count > 0:
                logger.info(f"Successfully notified {success_count} admin(s)")
                return True
            else:
                logger.warning("No admins were notified")
                return False

        await bot.session.close()
        await engine.dispose()

    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(
            "Usage: python scripts/notify_admin.py 'Message text' [--critical]"
        )
        sys.exit(1)

    message = sys.argv[1]
    critical = "--critical" in sys.argv

    # Add prefix for critical messages
    if critical:
        message = f"🚨 **КРИТИЧНО**\n\n{message}"

    success = asyncio.run(notify_admins(message, critical=critical))

    if success:
        print("✅ Admin notification sent successfully")
        sys.exit(0)
    else:
        print("❌ Failed to send admin notification")
        sys.exit(1)


if __name__ == "__main__":
    main()
