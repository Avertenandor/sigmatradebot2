"""
Bot main entry point.

Initializes and runs the Telegram bot with aiogram 3.x.
"""

import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.database import async_session_maker
from app.config.settings import settings
from bot.middlewares.database import DatabaseMiddleware
from bot.middlewares.request_id import RequestIDMiddleware


async def main() -> None:
    """Initialize and run the bot."""
    # Configure logger
    logger.add(
        "logs/bot.log",
        rotation="1 day",
        retention="7 days",
        level="INFO",
    )

    logger.info("Starting SigmaTrade Bot...")

    # Initialize bot
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.MARKDOWN,
        ),
    )

    # Initialize dispatcher
    dp = Dispatcher()

    # Register middlewares (PART5: RequestID must be first!)
    dp.update.middleware(RequestIDMiddleware())
    dp.update.middleware(
        DatabaseMiddleware(session_pool=async_session_maker)
    )

    # Register handlers
    from bot.handlers import (
        deposit,
        menu,
        start,
        withdrawal,
        referral,
        profile,
        transaction,
        support,
    )
    from bot.handlers.admin import panel, users, withdrawals, broadcast

    # Core handlers
    dp.include_router(start.router)
    dp.include_router(menu.router)

    # User handlers
    dp.include_router(deposit.router)
    dp.include_router(withdrawal.router)
    dp.include_router(referral.router)
    dp.include_router(profile.router)
    dp.include_router(transaction.router)
    dp.include_router(support.router)

    # Admin handlers
    dp.include_router(panel.router)
    dp.include_router(users.router)
    dp.include_router(withdrawals.router)
    dp.include_router(broadcast.router)

    # Start polling
    logger.info("Bot started successfully")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Bot crashed: {e}")
        sys.exit(1)
