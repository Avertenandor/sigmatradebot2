"""
Redis cache warmup task.

R11-3: Warms up Redis cache after recovery by loading frequently used data.
Loads users, deposit levels, and system settings in batches.
"""

import asyncio
from typing import Any

import dramatiq
from loguru import logger

try:
    from redis.asyncio import Redis as AsyncRedis
except ImportError:
    import redis.asyncio as aioredis

    AsyncRedis = aioredis.Redis

from app.config.database import async_session_maker
from app.config.settings import settings
from app.repositories.deposit_level_version_repository import (
    DepositLevelVersionRepository,
)
from app.repositories.system_setting_repository import SystemSettingRepository
from app.repositories.user_repository import UserRepository


@dramatiq.actor(max_retries=3, time_limit=300_000)  # 5 min timeout
def warmup_redis_cache() -> dict:
    """
    Warm up Redis cache after recovery.

    R11-3: Loads frequently used data into Redis cache to reduce database load.

    Returns:
        Dict with loaded counts for each data type
    """
    logger.info("R11-3: Starting Redis cache warmup...")

    try:
        result = asyncio.run(_warmup_redis_cache_async())
        logger.info(
            f"R11-3: Redis cache warmup complete: "
            f"{result['users_loaded']} users, "
            f"{result['deposit_levels_loaded']} deposit levels, "
            f"{result['settings_loaded']} settings"
        )
        return result
    except Exception as e:
        logger.exception(f"R11-3: Redis cache warmup failed: {e}")
        return {
            "users_loaded": 0,
            "deposit_levels_loaded": 0,
            "settings_loaded": 0,
            "error": str(e),
        }


async def _warmup_redis_cache_async() -> dict:
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
        return {
            "users_loaded": 0,
            "deposit_levels_loaded": 0,
            "settings_loaded": 0,
            "error": "Redis not available",
        }

    users_loaded = 0
    deposit_levels_loaded = 0
    settings_loaded = 0

    try:
        async with async_session_maker() as session:
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

            # 3. Load system settings
            settings_repo = SystemSettingRepository(session)
            system_settings = await settings_repo.find_all()

            for setting in system_settings:
                try:
                    setting_key = f"system_setting:{setting.key}"
                    await redis_client.set(
                        setting_key, setting.value, ex=1800
                    )  # 30 min TTL
                    settings_loaded += 1
                except Exception as e:
                    logger.warning(
                        f"R11-3: Failed to cache setting {setting.key}: {e}"
                    )

            logger.info(f"R11-3: Cached {settings_loaded} system settings")

    except Exception as e:
        logger.error(f"R11-3: Error during cache warmup: {e}", exc_info=True)
    finally:
        await redis_client.close()

    return {
        "users_loaded": users_loaded,
        "deposit_levels_loaded": deposit_levels_loaded,
        "settings_loaded": settings_loaded,
    }

