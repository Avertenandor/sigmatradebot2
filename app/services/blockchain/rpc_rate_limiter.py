"""
RPC Rate Limiter for Web3 calls.

Provides rate limiting for QuickNode RPC endpoints using:
- Semaphore for max concurrent requests
- Token bucket algorithm for RPS limit
"""

import asyncio
import time
from collections import deque
from typing import Any

from loguru import logger


class RPCRateLimiter:
    """
    Rate limiter for Web3 RPC calls.

    Features:
    - Semaphore for max concurrent requests (default: 10)
    - Token bucket for RPS limit (default: 25/sec for $49 plan)
    - Stats tracking (requests per minute, avg response time, errors)
    """

    def __init__(
        self, max_concurrent: int = 10, max_rps: int = 25
    ) -> None:
        """
        Initialize RPC rate limiter.

        Args:
            max_concurrent: Maximum concurrent RPC requests
            max_rps: Maximum requests per second (token bucket capacity)
        """
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._tokens = max_rps
        self._max_tokens = max_rps
        self._lock = asyncio.Lock()
        self._last_refill = time.time()
        self._refill_rate = max_rps  # Tokens per second

        # Stats tracking
        self._request_times: deque[float] = deque(maxlen=60)  # Last 60 seconds
        self._response_times: deque[float] = deque(maxlen=100)  # Last 100 requests
        self._error_count = 0
        self._total_requests = 0

    async def __aenter__(self) -> "RPCRateLimiter":
        """
        Enter async context manager.

        Acquires semaphore and waits for token.
        """
        await self._semaphore.acquire()
        await self._wait_for_token()
        self._start_time = time.time()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Exit async context manager.

        Releases semaphore and tracks request stats.
        """
        try:
            # Track request completion
            end_time = time.time()
            response_time = (end_time - self._start_time) * 1000  # ms
            self._request_times.append(end_time)
            self._response_times.append(response_time)
            self._total_requests += 1

            # Record error if exception occurred
            if exc_type is not None:
                self.record_error()
        finally:
            self._semaphore.release()

    async def _wait_for_token(self) -> None:
        """
        Wait for available token using token bucket algorithm.

        Refills tokens at a constant rate (max_rps per second).
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_refill

            # Refill tokens based on elapsed time
            if elapsed > 0:
                tokens_to_add = elapsed * self._refill_rate
                self._tokens = min(
                    self._max_tokens, self._tokens + tokens_to_add
                )
                self._last_refill = now

            # Wait if no tokens available
            if self._tokens < 1:
                wait_time = (1 - self._tokens) / self._refill_rate
                await asyncio.sleep(wait_time)
                # Refill after wait
                now = time.time()
                elapsed = now - self._last_refill
                tokens_to_add = elapsed * self._refill_rate
                self._tokens = min(
                    self._max_tokens, self._tokens + tokens_to_add
                )
                self._last_refill = now

            # Consume token
            self._tokens -= 1

    def record_error(self) -> None:
        """Record an RPC error."""
        self._error_count += 1

    def get_stats(self) -> dict[str, Any]:
        """
        Get RPC usage statistics.

        Returns:
            Dict with:
            - requests_last_minute: int
            - avg_response_time_ms: float
            - error_count: int
            - total_requests: int
        """
        now = time.time()
        # Count requests in last 60 seconds
        requests_last_minute = sum(
            1 for req_time in self._request_times
            if now - req_time < 60
        )

        # Calculate average response time
        avg_response_time_ms = 0.0
        if self._response_times:
            avg_response_time_ms = sum(self._response_times) / len(
                self._response_times
            )

        return {
            "requests_last_minute": requests_last_minute,
            "avg_response_time_ms": round(avg_response_time_ms, 2),
            "error_count": self._error_count,
            "total_requests": self._total_requests,
        }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._request_times.clear()
        self._response_times.clear()
        self._error_count = 0
        self._total_requests = 0

