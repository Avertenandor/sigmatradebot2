"""
Redis recovery task.

R11-3: Handles recovery of notification queue and FSM states when Redis recovers.
Migrates data from PostgreSQL fallback back to Redis.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import dramatiq
from loguru import logger

try:
    from redis.asyncio import Redis as AsyncRedis
except ImportError:
    import redis.asyncio as aioredis

    AsyncRedis = aioredis.Redis

from aiogram.fsm.storage.redis import RedisStorage

from app.config.database import async_session_maker
from app.config.settings import settings
from app.models.notification_queue_fallback import NotificationQueueFallback
from app.models.user_fsm_state import UserFsmState
from app.repositories.user_repository import UserRepository


@dramatiq.actor(max_retries=3, time_limit=600_000)  # 10 min timeout
def recover_redis_data() -> dict:
    """
    Recover notification queue and FSM states when Redis recovers.

    R11-3: Migrates data from PostgreSQL fallback back to Redis.

    Returns:
        Dict with migration results
    """
    logger.info("R11-3: Starting Redis recovery process...")

    try:
        result = asyncio.run(_recover_redis_data_async())
        logger.info(
            f"R11-3: Redis recovery complete: "
            f"{result['notifications_migrated']} notifications, "
            f"{result['fsm_states_migrated']} FSM states"
        )
        return result
    except Exception as e:
        logger.exception(f"R11-3: Redis recovery failed: {e}")
        return {
            "notifications_migrated": 0,
            "fsm_states_migrated": 0,
            "error": str(e),
        }


async def _recover_redis_data_async() -> dict:
    """Async implementation of Redis recovery."""
    # Check if Redis is available
    try:
        redis_client = AsyncRedis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            decode_responses=True,
        )
        await redis_client.ping()
        logger.info("R11-3: Redis is available, starting recovery")
    except Exception as e:
        logger.warning(f"R11-3: Redis not available for recovery: {e}")
        return {
            "notifications_migrated": 0,
            "fsm_states_migrated": 0,
            "error": "Redis not available",
        }

    notifications_migrated = 0
    fsm_states_migrated = 0

    try:
        async with async_session_maker() as session:
            # 1. Migrate notification queue from PostgreSQL to Redis
            from sqlalchemy import select

            # Get pending notifications
            stmt = (
                select(NotificationQueueFallback)
                .where(NotificationQueueFallback.processed_at.is_(None))
                .order_by(
                    NotificationQueueFallback.priority.desc(),
                    NotificationQueueFallback.created_at.asc(),
                )
                .limit(1000)  # Process in batches
            )

            result = await session.execute(stmt)
            pending_notifications = list(result.scalars().all())

            if pending_notifications:
                logger.info(
                    f"R11-3: Migrating {len(pending_notifications)} "
                    "notifications from PostgreSQL to Redis"
                )

                for notification in pending_notifications:
                    try:
                        # Add to Redis queue (using JSON for proper serialization)
                        queue_key = (
                            "notification_queue:critical"
                            if notification.priority >= 100
                            else "notification_queue:normal"
                        )
                        notification_data = {
                            "user_id": notification.user_id,
                            "type": notification.notification_type,
                            "payload": notification.payload,
                            "created_at": notification.created_at.isoformat(),
                        }
                        await redis_client.lpush(
                            queue_key, json.dumps(notification_data)
                        )

                        # Mark as processed
                        notification.processed_at = datetime.now(UTC)
                        notifications_migrated += 1

                    except Exception as e:
                        logger.error(
                            f"R11-3: Failed to migrate notification "
                            f"{notification.id}: {e}"
                        )

                await session.commit()
                logger.info(
                    f"R11-3: Migrated {notifications_migrated} notifications"
                )

            # 2. Migrate FSM states from PostgreSQL to Redis
            user_repo = UserRepository(session)

            # Get active FSM states (updated in last 24 hours)
            cutoff_time = datetime.now(UTC) - timedelta(hours=24)
            stmt = (
                select(UserFsmState)
                .where(UserFsmState.updated_at >= cutoff_time)
                .where(UserFsmState.state.isnot(None))
            )

            result = await session.execute(stmt)
            active_fsm_states = list(result.scalars().all())

            if active_fsm_states:
                logger.info(
                    f"R11-3: Migrating {len(active_fsm_states)} "
                    "FSM states from PostgreSQL to Redis"
                )

                redis_storage = RedisStorage(redis=redis_client)

                for fsm_state in active_fsm_states:
                    try:
                        user = await user_repo.get_by_id(fsm_state.user_id)
                        if not user:
                            continue

                        # Create storage key
                        from aiogram.fsm.storage.base import StorageKey

                        storage_key = StorageKey(
                            chat_id=user.telegram_id,
                            user_id=user.telegram_id,
                            bot_id=int(settings.telegram_bot_token.split(":")[0]),
                        )

                        # Set state in Redis
                        if fsm_state.state:
                            await redis_storage.set_state(
                                storage_key, state=fsm_state.state
                            )

                        # Set data in Redis
                        if fsm_state.data:
                            await redis_storage.set_data(
                                storage_key, data=fsm_state.data
                            )

                        fsm_states_migrated += 1

                    except Exception as e:
                        logger.error(
                            f"R11-3: Failed to migrate FSM state "
                            f"for user {fsm_state.user_id}: {e}"
                        )

                logger.info(
                    f"R11-3: Migrated {fsm_states_migrated} FSM states"
                )

    except Exception as e:
        logger.error(f"R11-3: Error during Redis recovery: {e}", exc_info=True)
    finally:
        await redis_client.close()

    return {
        "notifications_migrated": notifications_migrated,
        "fsm_states_migrated": fsm_states_migrated,
    }

