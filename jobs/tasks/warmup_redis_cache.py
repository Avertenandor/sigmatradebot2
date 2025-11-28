"""
Redis cache warmup task.

R11-3: Warms up Redis cache after recovery by loading frequently used data.
Loads users, deposit levels, and system settings in batches.
"""

import asyncio
from typing import Any

import dramatiq
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

try:
    from redis.asyncio import Redis as AsyncRedis
except ImportError:
    import redis.asyncio as aioredis

    AsyncRedis = aioredis.Redis

from app.config.settings import settings
from app.repositories.deposit_level_version_repository import (
    DepositLevelVersionRepository,
)
from app.repositories.global_settings_repository import GlobalSettingsRepository
from app.repositories.user_repository import UserRepository


@dramatiq.actor(max_retries=3, time_limit=300_000)  # 5 min timeout
def warmup_redis_cache() -> None:
    """
    Warm up Redis cache after recovery.

    R11-3: Loads frequently used data into Redis cache to reduce database load.
    """
    logger.info("R11-3: Starting Redis cache warmup...")

    try:
        asyncio.run(_warmup_redis_cache_async())
        logger.info("R11-3: Redis cache warmup complete")
    except Exception as e:
        logger.exception(f"R11-3: Redis cache warmup failed: {e}")


async def _warmup_redis_cache_async() -> None:
    """Async implementation of Redis cache warmup."""
    # Initialize Redis client
    try:
        redis_client = AsyncRedis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            decode_responses=True,
        )
        await redis_client.ping()
    except Exception as e:
        logger.error(f"R11-3: Redis not available for warmup: {e}")
        return

    users_loaded = 0
    deposit_levels_loaded = 0
    settings_loaded = 0

    # Create local engine to avoid event loop issues in threaded worker
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
            # 1. Load active users (batch of 1000)
            user_repo = UserRepository(session)
            users = await user_repo.find_all(limit=1000)

            for user in users:
                try:
                    # Cache user by telegram_id
                    user_key = f"user:telegram_id:{user.telegram_id}"
                    user_data = {
                        "id": str(user.id),
                        "telegram_id": str(user.telegram_id),
                        "wallet_address": user.wallet_address or "",
                        "is_verified": str(user.is_verified),
                    }
                    await redis_client.hset(user_key, mapping=user_data)
                    await redis_client.expire(user_key, 3600)  # 1 hour TTL

                    # Cache user by ID
                    user_id_key = f"user:id:{user.id}"
                    await redis_client.hset(user_id_key, mapping=user_data)
                    await redis_client.expire(user_id_key, 3600)

                    users_loaded += 1
                except Exception as e:
                    logger.warning(
                        f"R11-3: Failed to cache user {user.id}: {e}"
                    )

            logger.info(f"R11-3: Cached {users_loaded} users")

            # 2. Load deposit levels
            level_repo = DepositLevelVersionRepository(session)
            for level in range(1, 6):
                try:
                    level_version = await level_repo.get_current_version(level)
                    if level_version:
                        level_key = f"deposit_level:{level}:current"
                        level_data = {
                            "id": str(level_version.id),
                            "level": str(level),
                            "amount": str(level_version.amount),
                            "roi_percent": str(level_version.roi_percent),
                            "roi_cap_percent": str(level_version.roi_cap_percent),
                            "is_active": str(level_version.is_active),
                        }
                        await redis_client.hset(level_key, mapping=level_data)
                        await redis_client.expire(level_key, 1800)  # 30 min TTL
                        deposit_levels_loaded += 1
                except Exception as e:
                    logger.warning(
                        f"R11-3: Failed to cache deposit level {level}: {e}"
                    )

            logger.info(
                f"R11-3: Cached {deposit_levels_loaded} deposit levels"
            )

            # 3. Load global settings
            settings_repo = GlobalSettingsRepository(session)
            global_settings = await settings_repo.get_settings()

            try:
                import json
                from decimal import Decimal
                
                # Convert settings to dict for caching
                settings_dict = {
                    "min_withdrawal_amount": str(global_settings.min_withdrawal_amount),
                    "daily_withdrawal_limit": str(global_settings.daily_withdrawal_limit) if global_settings.daily_withdrawal_limit else None,
                    "is_daily_limit_enabled": global_settings.is_daily_limit_enabled,
                    "auto_withdrawal_enabled": global_settings.auto_withdrawal_enabled,
                    "active_rpc_provider": global_settings.active_rpc_provider,
                    "is_auto_switch_enabled": global_settings.is_auto_switch_enabled,
                    "max_open_deposit_level": global_settings.max_open_deposit_level,
                    "roi_settings": global_settings.roi_settings,
                }
                
                await redis_client.set(
                    "global_settings", json.dumps(settings_dict), ex=1800
                )  # 30 min TTL
                settings_loaded = 1
                logger.info("R11-3: Cached global settings")
            except Exception as e:
                logger.warning(f"R11-3: Failed to cache global settings: {e}")

    except Exception as e:
        logger.error(f"R11-3: Error during cache warmup: {e}", exc_info=True)
    finally:
        await redis_client.close()
        await local_engine.dispose()


