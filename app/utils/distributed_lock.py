"""
Distributed lock utility using Redis with PostgreSQL fallback.

R15-4, R15-5: Prevents race conditions between roles and concurrent operations.
"""

import asyncio
import hashlib
import time
from contextlib import asynccontextmanager
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

try:
    import redis.asyncio as redis
except ImportError:
    redis = None  # type: ignore


class DistributedLock:
    """
    R15-4, R15-5: Distributed lock using Redis with PostgreSQL fallback.

    Prevents concurrent operations on the same resource.
    Falls back to PostgreSQL advisory locks if Redis is unavailable.
    """

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        session: AsyncSession | None = None,
        default_timeout: int = 60,
    ) -> None:
        """
        Initialize distributed lock.

        Args:
            redis_client: Redis client (primary)
            session: Database session (fallback for PostgreSQL advisory locks)
            default_timeout: Default lock timeout in seconds
        """
        self.redis_client = redis_client
        self.session = session
        self.default_timeout = default_timeout

    def _key_to_advisory_id(self, key: str) -> int:
        """
        Convert lock key to PostgreSQL advisory lock ID.

        PostgreSQL advisory locks use int8 (64-bit integers).
        We hash the key to get a consistent integer.

        Args:
            key: Lock key

        Returns:
            Advisory lock ID
        """
        # Use hash to convert string to int64
        # PostgreSQL advisory locks use int8, so we need a 64-bit integer
        hash_obj = hashlib.sha256(key.encode())
        # Take first 8 bytes and convert to int64 (signed)
        hash_bytes = hash_obj.digest()[:8]
        # Convert to signed int64
        advisory_id = int.from_bytes(hash_bytes, byteorder="big", signed=True)
        # Ensure it's within PostgreSQL int8 range
        return advisory_id % (2**63 - 1)

    async def _acquire_postgresql_lock(
        self,
        key: str,
        blocking: bool = False,
        blocking_timeout: float | None = None,
    ) -> bool:
        """
        Acquire PostgreSQL advisory lock (fallback).

        R15-4, R15-5: Uses pg_try_advisory_lock for non-blocking,
        pg_advisory_lock for blocking.

        Args:
            key: Lock key
            blocking: If True, wait for lock
            blocking_timeout: Max time to wait

        Returns:
            True if lock acquired
        """
        if not self.session:
            logger.warning("Database session not available for PostgreSQL lock")
            return False

        advisory_id = self._key_to_advisory_id(key)

        try:
            if blocking:
                # Use pg_advisory_lock (blocking) with timeout
                if blocking_timeout:
                    # Set statement timeout
                    await self.session.execute(
                        text(f"SET LOCAL statement_timeout = {int(blocking_timeout * 1000)}")
                    )

                # Try to acquire lock (blocking)
                result = await self.session.execute(
                    text("SELECT pg_try_advisory_lock(:lock_id)"),
                    {"lock_id": advisory_id},
                )
                acquired = result.scalar()

                if not acquired and blocking_timeout:
                    # If blocking with timeout, wait with retries
                    end_time = time.time() + blocking_timeout
                    while time.time() < end_time:
                        await asyncio.sleep(0.1)
                        result = await self.session.execute(
                            text("SELECT pg_try_advisory_lock(:lock_id)"),
                            {"lock_id": advisory_id},
                        )
                        acquired = result.scalar()
                        if acquired:
                            break

                if acquired:
                    logger.debug(f"PostgreSQL advisory lock acquired: {key} (id={advisory_id})")
                    return True
                else:
                    logger.warning(f"PostgreSQL advisory lock timeout: {key}")
                    return False
            else:
                # Non-blocking: use pg_try_advisory_lock
                result = await self.session.execute(
                    text("SELECT pg_try_advisory_lock(:lock_id)"),
                    {"lock_id": advisory_id},
                )
                acquired = result.scalar()

                if acquired:
                    logger.debug(f"PostgreSQL advisory lock acquired: {key} (id={advisory_id})")
                else:
                    logger.debug(f"PostgreSQL advisory lock not available: {key}")

                return bool(acquired)

        except Exception as e:
            logger.error(f"Error acquiring PostgreSQL advisory lock {key}: {e}")
            return False

    async def _release_postgresql_lock(self, key: str) -> bool:
        """
        Release PostgreSQL advisory lock.

        Args:
            key: Lock key

        Returns:
            True if released
        """
        if not self.session:
            return False

        advisory_id = self._key_to_advisory_id(key)

        try:
            result = await self.session.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": advisory_id},
            )
            released = result.scalar()

            if released:
                logger.debug(f"PostgreSQL advisory lock released: {key} (id={advisory_id})")
            return bool(released)

        except Exception as e:
            logger.error(f"Error releasing PostgreSQL advisory lock {key}: {e}")
            return False

    async def acquire(
        self,
        key: str,
        timeout: int | None = None,
        blocking: bool = False,
        blocking_timeout: float | None = None,
    ) -> bool:
        """
        Acquire distributed lock.

        R15-4, R15-5: Tries Redis first, falls back to PostgreSQL if Redis unavailable.

        Args:
            key: Lock key (e.g., "user:123:operation")
            timeout: Lock timeout in seconds (default: self.default_timeout)
            blocking: If True, wait for lock to be available
            blocking_timeout: Max time to wait for lock (seconds)

        Returns:
            True if lock acquired, False otherwise
        """
        # Try Redis first
        if self.redis_client:
            try:
                return await self._acquire_redis_lock(
                    key, timeout, blocking, blocking_timeout
                )
            except Exception as e:
                logger.warning(
                    f"Redis lock failed for {key}, falling back to PostgreSQL: {e}"
                )

        # Fallback to PostgreSQL
        if self.session:
            return await self._acquire_postgresql_lock(key, blocking, blocking_timeout)

        logger.warning(
            "Neither Redis nor database session available, lock not acquired"
        )
        return False

    async def _acquire_redis_lock(
        self,
        key: str,
        timeout: int | None = None,
        blocking: bool = False,
        blocking_timeout: float | None = None,
    ) -> bool:
        """
        Acquire Redis lock (internal method).

        Args:
            key: Lock key
            timeout: Lock timeout
            blocking: If True, wait
            blocking_timeout: Max wait time

        Returns:
            True if acquired
        """
        if not self.redis_client:
            return False

        timeout = timeout or self.default_timeout
        lock_key = f"lock:{key}"
        lock_value = f"{time.time()}:{id(self)}"  # Unique value

        if blocking:
            # Wait for lock with timeout
            end_time = (
                time.time() + blocking_timeout
                if blocking_timeout
                else None
            )

            while True:
                acquired = await self.redis_client.set(
                    lock_key,
                    lock_value,
                    nx=True,  # Only set if not exists
                    ex=timeout,  # Expire after timeout
                )

                if acquired:
                    logger.debug(f"Distributed lock acquired: {key}")
                    return True

                if end_time and time.time() >= end_time:
                    logger.warning(
                        f"Distributed lock timeout: {key} "
                        f"(waited {blocking_timeout}s)"
                    )
                    return False

                # Wait before retry
                await asyncio.sleep(0.1)

        else:
            # Try once, don't wait
            acquired = await self.redis_client.set(
                lock_key,
                lock_value,
                nx=True,
                ex=timeout,
            )

            if acquired:
                logger.debug(f"Distributed lock acquired: {key}")
                return True

            logger.debug(f"Distributed lock not available: {key}")
            return False

        timeout = timeout or self.default_timeout
        lock_key = f"lock:{key}"
        lock_value = f"{time.time()}:{id(self)}"  # Unique value

        try:
            if blocking:
                # Wait for lock with timeout
                end_time = (
                    time.time() + blocking_timeout
                    if blocking_timeout
                    else None
                )

                while True:
                    acquired = await self.redis_client.set(
                        lock_key,
                        lock_value,
                        nx=True,  # Only set if not exists
                        ex=timeout,  # Expire after timeout
                    )

                    if acquired:
                        logger.debug(f"Distributed lock acquired: {key}")
                        return True

                    if end_time and time.time() >= end_time:
                        logger.warning(
                            f"Distributed lock timeout: {key} "
                            f"(waited {blocking_timeout}s)"
                        )
                        return False

                    # Wait before retry
                    await asyncio.sleep(0.1)

            else:
                # Try once, don't wait
                acquired = await self.redis_client.set(
                    lock_key,
                    lock_value,
                    nx=True,
                    ex=timeout,
                )

                if acquired:
                    logger.debug(f"Distributed lock acquired: {key}")
                    return True

                logger.debug(f"Distributed lock not available: {key}")
                return False

        except Exception as e:
            logger.error(f"Error acquiring distributed lock {key}: {e}")
            return False  # Fail open

    async def release(self, key: str) -> bool:
        """
        Release distributed lock.

        R15-4, R15-5: Releases Redis or PostgreSQL lock depending on what was used.

        Args:
            key: Lock key

        Returns:
            True if released, False otherwise
        """
        # Try Redis first
        if self.redis_client:
            try:
                lock_key = f"lock:{key}"
                deleted = await self.redis_client.delete(lock_key)
                if deleted:
                    logger.debug(f"Distributed lock released: {key}")
                    return deleted > 0
            except Exception as e:
                logger.warning(
                    f"Redis lock release failed for {key}, trying PostgreSQL: {e}"
                )

        # Fallback to PostgreSQL
        if self.session:
            return await self._release_postgresql_lock(key)

        return False

    async def is_locked(self, key: str) -> bool:
        """
        Check if lock is currently held.

        R15-4, R15-5: Checks Redis or PostgreSQL depending on availability.

        Args:
            key: Lock key

        Returns:
            True if locked
        """
        # Try Redis first
        if self.redis_client:
            try:
                lock_key = f"lock:{key}"
                exists = await self.redis_client.exists(lock_key)
                return exists == 1
            except Exception as e:
                logger.warning(
                    f"Redis lock check failed for {key}, trying PostgreSQL: {e}"
                )

        # Fallback to PostgreSQL
        if self.session:
            try:
                advisory_id = self._key_to_advisory_id(key)
                result = await self.session.execute(
                    text("SELECT pg_try_advisory_lock(:lock_id)"),
                    {"lock_id": advisory_id},
                )
                # If we can acquire it, it wasn't locked
                acquired = result.scalar()
                if acquired:
                    # Release immediately since we just checked
                    await self._release_postgresql_lock(key)
                    return False
                return True  # Couldn't acquire, so it's locked
            except Exception as e:
                logger.error(f"Error checking PostgreSQL lock {key}: {e}")

        return False

    @asynccontextmanager
    async def lock(
        self,
        key: str,
        timeout: int | None = None,
        blocking: bool = False,
        blocking_timeout: float | None = None,
    ):
        """
        Context manager for distributed lock.

        R15-4, R15-5: Use this for critical operations.

        Example:
            async with distributed_lock.lock("user:123:withdrawal"):
                # Critical operation
                await process_withdrawal(user_id=123)

        Args:
            key: Lock key
            timeout: Lock timeout in seconds
            blocking: If True, wait for lock
            blocking_timeout: Max time to wait

        Yields:
            True if lock acquired, False otherwise
        """
        acquired = await self.acquire(
            key=key,
            timeout=timeout,
            blocking=blocking,
            blocking_timeout=blocking_timeout,
        )

        try:
            yield acquired
        finally:
            if acquired:
                await self.release(key)


# Global instance (will be initialized with Redis client)
_distributed_lock: DistributedLock | None = None


def get_distributed_lock(
    redis_client: redis.Redis | None = None,
    session: AsyncSession | None = None,
) -> DistributedLock:
    """
    Get distributed lock instance.

    R15-4, R15-5: Creates lock with Redis (primary) and PostgreSQL (fallback).

    Args:
        redis_client: Optional Redis client (primary)
        session: Optional database session (fallback for PostgreSQL advisory locks)

    Returns:
        DistributedLock instance
    """
    global _distributed_lock

    if redis_client or session:
        return DistributedLock(redis_client=redis_client, session=session)

    if _distributed_lock is None:
        _distributed_lock = DistributedLock()

    return _distributed_lock

