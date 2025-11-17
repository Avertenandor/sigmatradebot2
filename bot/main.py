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
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import ErrorEvent
from loguru import logger

try:
    from redis.asyncio import Redis as AsyncRedis
except ImportError:
    # Fallback for older redis versions
    import redis.asyncio as aioredis

    AsyncRedis = aioredis.Redis

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.database import async_session_maker  # noqa: E402
from app.config.settings import settings  # noqa: E402
from app.services.blockchain_service import (
    init_blockchain_service,  # noqa: E402
)
from app.utils.admin_init import ensure_default_super_admin  # noqa: E402
from bot.middlewares.auth import AuthMiddleware  # noqa: E402
from bot.middlewares.ban_middleware import BanMiddleware  # noqa: E402
from bot.middlewares.database import DatabaseMiddleware  # noqa: E402
from bot.middlewares.logger_middleware import LoggerMiddleware  # noqa: E402
from bot.middlewares.menu_state_clear import (
    MenuStateClearMiddleware,  # noqa: E402
)
from bot.middlewares.rate_limit_middleware import (
    RateLimitMiddleware,  # noqa: E402
)
from bot.middlewares.request_id import RequestIDMiddleware  # noqa: E402


async def main() -> None:  # noqa: C901
    """Initialize and run the bot."""
    # Configure logger
    logger.add(
        "logs/bot.log",
        rotation="1 day",
        retention="7 days",
        level="INFO",
    )

    logger.info("Starting SigmaTrade Bot...")

    # Validate environment variables (basic check)
    try:
        # Quick validation of critical settings
        if (
            not settings.telegram_bot_token
            or "your_" in settings.telegram_bot_token.lower()
        ):
            logger.error("TELEGRAM_BOT_TOKEN is not properly configured")
        if (
            not settings.database_url
            or "your_" in settings.database_url.lower()
        ):
            logger.error("DATABASE_URL is not properly configured")
        if (
            not settings.wallet_private_key
            or "your_" in settings.wallet_private_key.lower()
        ):
            logger.warning(
                "WALLET_PRIVATE_KEY is not configured. "
                "Bot will start, but blockchain operations will be unavailable. "
                "Set key via /wallet_menu in bot interface."
            )
    except Exception as e:
        logger.warning(f"Could not validate environment: {e}")

    # Initialize BlockchainService
    try:
        init_blockchain_service(
            rpc_url=settings.rpc_url,
            usdt_contract=settings.usdt_contract_address,
            wallet_private_key=settings.wallet_private_key,
        )
        logger.info("BlockchainService initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize BlockchainService: {e}")
        logger.warning("Bot will continue, but blockchain operations may fail")

    # Initialize Redis for FSM storage
    redis_client = None
    try:
        redis_client = AsyncRedis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            decode_responses=True,
        )
        # Test Redis connection
        await redis_client.ping()
        logger.info("Redis connection established for FSM storage")
        storage = RedisStorage(redis=redis_client)
    except Exception as e:
        logger.error(f"Failed to initialize Redis storage: {e}")
        logger.warning(
            "Falling back to MemoryStorage (states will not persist)"
        )
        from aiogram.fsm.storage.memory import MemoryStorage

        storage = MemoryStorage()
        redis_client = None

    # Initialize bot
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.MARKDOWN,
        ),
    )

    # Initialize dispatcher with Redis storage
    dp = Dispatcher(storage=storage)

    # Register middlewares (PART5: RequestID must be first!)
    dp.update.middleware(RequestIDMiddleware())
    dp.update.middleware(LoggerMiddleware())
    dp.update.middleware(DatabaseMiddleware(session_pool=async_session_maker))
    # Menu state clear must be after DatabaseMiddleware (needs session)
    # but before AuthMiddleware to clear state early
    dp.update.middleware(MenuStateClearMiddleware())
    dp.update.middleware(AuthMiddleware())
    dp.update.middleware(BanMiddleware())

    # Rate limiting (optional, requires Redis)
    if redis_client:
        try:
            dp.update.middleware(
                RateLimitMiddleware(
                    redis_client=redis_client,
                    user_limit=30,  # requests per window
                    user_window=60,  # seconds
                )
            )
            logger.info("Rate limiting enabled")
        except Exception as e:
            logger.warning(f"Rate limiting disabled: {e}")

    # Register error handler (MUST BE FIRST)
    @dp.error()
    async def error_handler(event: ErrorEvent) -> bool:
        """Global error handler for unhandled exceptions."""
        logger.exception(
            f"Unhandled error in bot: {event.exception.__class__.__name__}: "
            f"{event.exception}",
            extra={"update": str(event.update) if event.update else None},
        )

        # Try to send error message to user
        try:
            if event.update and event.update.message:
                await event.update.message.answer(
                    "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже "
                    "или обратитесь в поддержку."
                )
        except Exception as send_error:
            logger.error(f"Failed to send error message: {send_error}")

        return True  # Mark error as handled

    # Register handlers
    from bot.handlers import (
        appeal,
        deposit,
        # finpass_recovery,  # Temporarily disabled due to encoding issues
        instructions,
        menu,
        profile,
        referral,
        start,
        support,
        transaction,
        verification,
        withdrawal,
    )
    from bot.handlers.admin import (
        blacklist,
        broadcast,
        deposit_settings,
        # finpass_recovery as admin_finpass,
            # Temporarily disabled due to encoding issues
        management,
        panel,
        users,
        wallet_key_setup,
        wallets,
        withdrawals,
    )

    # Core handlers (menu must be registered BEFORE deposit/withdrawal
    # to have priority over FSM state handlers)
    dp.include_router(start.router)
    dp.include_router(menu.router)

    # User handlers (registered AFTER menu to ensure menu handlers
    # process menu buttons first, even if user is in FSM state)
    dp.include_router(deposit.router)
    dp.include_router(withdrawal.router)
    dp.include_router(referral.router)
    dp.include_router(profile.router)
    dp.include_router(transaction.router)
    dp.include_router(support.router)
    dp.include_router(verification.router)
    # dp.include_router(finpass_recovery.router)  # Temporarily disabled
    dp.include_router(instructions.router)
    dp.include_router(appeal.router)

    # Admin handlers (wallet_key_setup must be first for security)
    dp.include_router(wallet_key_setup.router)
    dp.include_router(panel.router)
    dp.include_router(users.router)
    dp.include_router(withdrawals.router)
    dp.include_router(broadcast.router)
    dp.include_router(blacklist.router)
    dp.include_router(deposit_settings.router)
    # dp.include_router(admin_finpass.router)  # Temporarily disabled
    dp.include_router(management.router)
    dp.include_router(wallets.router)

    # Test bot connection
    try:
        bot_info = await bot.get_me()
        logger.info(f"Bot connected: @{bot_info.username} (ID: {bot_info.id})")
    except Exception as e:
        logger.error(f"Failed to connect to Telegram API: {e}")
        raise

    # Initialize default super admin (after bot connection is established)
    logger.info("Initializing default super admin...")
    try:
        async with async_session_maker() as session:
            await ensure_default_super_admin(session, bot=bot)
        logger.info("Default super admin initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize default super admin: {e}")
        logger.warning(
            "Bot will continue, but admin may need to be created manually"
        )

    # Start polling
    logger.info("Bot started successfully")

    try:
        logger.info("Starting polling...")
        await dp.start_polling(
            bot, allowed_updates=dp.resolve_used_update_types()
        )
    except Exception as e:
        logger.exception(f"Polling error: {e}")
        raise
    finally:
        if redis_client:
            await redis_client.aclose()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Bot crashed: {e}")
        sys.exit(1)
