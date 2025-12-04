"""
Nonce Manager for blockchain transactions.

Prevents race conditions when sending multiple transactions by using distributed locks.
"""

import asyncio
from typing import Any

from loguru import logger
from web3 import Web3, AsyncWeb3

try:
    import redis.asyncio as redis
except ImportError:
    redis = None  # type: ignore


class NonceManager:
    """
    Manages nonce allocation for blockchain transactions with distributed locking.

    Features:
    - Uses 'latest' block for nonce (not 'pending' to avoid race conditions)
    - Distributed lock via Redis to prevent concurrent nonce conflicts
    - Fallback to local lock if Redis unavailable
    """

    def __init__(
        self,
        redis_client: Any | None = None,
        address: str | None = None,
    ) -> None:
        """
        Initialize nonce manager.

        Args:
            redis_client: Redis client for distributed locking
            address: Wallet address for nonce tracking
        """
        self.redis = redis_client
        self.address = address.lower() if address else None
        self.lock_key = f"nonce_lock:{self.address}" if self.address else None

        # Local asyncio lock as fallback
        self._local_lock = asyncio.Lock()

    async def get_next_nonce(self, web3: Web3 | AsyncWeb3) -> int:
        """
        Get next available nonce for address with distributed locking.

        Uses 'latest' block for nonce to avoid race conditions with 'pending'.

        Args:
            web3: Web3 or AsyncWeb3 instance

        Returns:
            Next nonce value
        """
        if not self.address:
            raise ValueError("Address not configured in NonceManager")

        # Use distributed lock if Redis available
        if self.redis and self.lock_key:
            return await self._get_nonce_with_redis_lock(web3)
        else:
            # Fallback to local lock
            logger.warning(
                "Redis not available for nonce locking, using local lock. "
                "This may cause race conditions in multi-process environments."
            )
            return await self._get_nonce_with_local_lock(web3)

    async def _get_nonce_with_redis_lock(self, web3: Web3 | AsyncWeb3) -> int:
        """
        Get nonce with Redis distributed lock.

        Args:
            web3: Web3 or AsyncWeb3 instance

        Returns:
            Next nonce value
        """
        lock_timeout = 30  # 30 seconds timeout for lock
        lock_acquired = False
        lock_value = f"nonce_lock_{asyncio.current_task().get_name() if asyncio.current_task() else 'unknown'}"

        try:
            # Try to acquire lock with timeout
            start_time = asyncio.get_event_loop().time()
            while not lock_acquired:
                # Use SET NX EX to atomically acquire lock
                lock_acquired = await self.redis.set(
                    self.lock_key,
                    lock_value,
                    nx=True,  # Only set if not exists
                    ex=lock_timeout,  # Expire after timeout
                )

                if lock_acquired:
                    break

                # Check if timeout exceeded
                if asyncio.get_event_loop().time() - start_time > lock_timeout:
                    raise TimeoutError(
                        f"Failed to acquire nonce lock for {self.address} "
                        f"after {lock_timeout}s"
                    )

                # Wait a bit before retrying
                await asyncio.sleep(0.1)

            # Get nonce from 'latest' block
            if isinstance(web3, AsyncWeb3):
                nonce = await web3.eth.get_transaction_count(self.address, 'latest')
            else:
                nonce = web3.eth.get_transaction_count(self.address, 'latest')

            logger.debug(f"Acquired nonce {nonce} for {self.address} with Redis lock")
            return nonce

        finally:
            # Release lock if we acquired it
            if lock_acquired:
                try:
                    # Only delete if we still own the lock (check value)
                    script = """
                    if redis.call("get", KEYS[1]) == ARGV[1] then
                        return redis.call("del", KEYS[1])
                    else
                        return 0
                    end
                    """
                    await self.redis.eval(script, 1, self.lock_key, lock_value)
                except Exception as e:
                    logger.warning(f"Failed to release Redis lock: {e}")

    async def _get_nonce_with_local_lock(self, web3: Web3 | AsyncWeb3) -> int:
        """
        Get nonce with local asyncio lock (fallback).

        Args:
            web3: Web3 or AsyncWeb3 instance

        Returns:
            Next nonce value
        """
        async with self._local_lock:
            # Get nonce from 'latest' block
            if isinstance(web3, AsyncWeb3):
                nonce = await web3.eth.get_transaction_count(self.address, 'latest')
            else:
                nonce = web3.eth.get_transaction_count(self.address, 'latest')

            logger.debug(f"Acquired nonce {nonce} for {self.address} with local lock")
            return nonce
