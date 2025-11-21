"""
Provider Manager for Web3.

Manages HTTP and WebSocket providers with fallback logic and health monitoring.
"""

import asyncio
from typing import Any

from loguru import logger
from web3 import AsyncHTTPProvider, AsyncWeb3
from web3.providers.async_base import AsyncBaseProvider

from .constants import WS_MAX_RECONNECT_ATTEMPTS, WS_RECONNECT_DELAY


class ProviderManager:
    """
    Manages Web3 providers (HTTP and WebSocket) with automatic fallback.

    Handles:
    - Provider health monitoring
    - Automatic reconnection
    - Fallback from WebSocket to HTTP
    """

    def __init__(
        self,
        https_url: str,
        wss_url: str,
        chain_id: int = 56,
    ) -> None:
        """
        Initialize provider manager.

        Args:
            https_url: QuickNode HTTPS endpoint URL
            wss_url: QuickNode WebSocket endpoint URL
            chain_id: BSC chain ID (56 for mainnet, 97 for testnet)
        """
        self.https_url = https_url
        self.wss_url = wss_url
        self.chain_id = chain_id

        # HTTP provider (always available)
        self._http_provider: AsyncHTTPProvider | None = None
        self._http_web3: AsyncWeb3 | None = None

        # WebSocket provider (for real-time events)
        self._ws_provider: AsyncBaseProvider | None = None
        self._ws_web3: AsyncWeb3 | None = None

        # Health status
        self._http_connected = False
        self._ws_connected = False
        self._ws_reconnect_attempts = 0

        logger.info(
            f"ProviderManager initialized for chain {chain_id}\n"
            f"  HTTP: {https_url[:50]}...\n"
            f"  WSS: {wss_url[:50]}..."
        )

    async def connect(self) -> None:
        """Connect to HTTP and WebSocket providers."""
        # Connect HTTP (always primary)
        await self._connect_http()

        # Connect WebSocket (for event monitoring)
        await self._connect_websocket()

    async def _connect_http(self) -> None:
        """Connect to HTTP provider."""
        try:
            self._http_provider = AsyncHTTPProvider(self.https_url)
            self._http_web3 = AsyncWeb3(self._http_provider)

            # Verify connection
            block = await self._http_web3.eth.block_number
            self._http_connected = True

            logger.success(
                f"HTTP provider connected successfully "
                f"(current block: {block})"
            )

        except Exception as e:
            self._http_connected = False
            logger.error(f"Failed to connect HTTP provider: {e}")
            raise

    async def _connect_websocket(self) -> None:
        """Connect to WebSocket provider."""
        try:
            # Note: web3.py 6.x uses AsyncIPCProvider or custom WebSocket
            # For now, we'll use HTTP for all operations
            # Real WebSocket support requires additional setup

            logger.warning(
                "WebSocket provider not yet implemented, "
                "using HTTP polling fallback"
            )
            self._ws_connected = False

        except Exception as e:
            self._ws_connected = False
            logger.warning(f"WebSocket connection failed: {e}")

    async def reconnect_websocket(self) -> bool:
        """
        Attempt to reconnect WebSocket provider.

        Returns:
            True if reconnection successful
        """
        if self._ws_reconnect_attempts >= WS_MAX_RECONNECT_ATTEMPTS:
            logger.error(
                "Max WebSocket reconnection attempts reached, "
                "using HTTP polling"
            )
            return False

        self._ws_reconnect_attempts += 1
        delay = WS_RECONNECT_DELAY * self._ws_reconnect_attempts

        logger.info(
            f"Attempting WebSocket reconnection "
            f"(attempt {self._ws_reconnect_attempts}/"
            f"{WS_MAX_RECONNECT_ATTEMPTS}) in {delay}s"
        )

        await asyncio.sleep(delay)

        try:
            await self._connect_websocket()
            if self._ws_connected:
                self._ws_reconnect_attempts = 0
                logger.success("WebSocket reconnected successfully")
                return True

        except Exception as e:
            logger.error(f"WebSocket reconnection failed: {e}")

        return False

    async def disconnect(self) -> None:
        """Disconnect all providers."""
        try:
            # Close HTTP provider
            if self._http_provider:
                # AsyncHTTPProvider doesn't have explicit close
                self._http_provider = None
                self._http_web3 = None
                self._http_connected = False

            # Close WebSocket provider
            if self._ws_provider:
                # Clean up WebSocket connection
                self._ws_provider = None
                self._ws_web3 = None
                self._ws_connected = False

            logger.info("All providers disconnected")

        except Exception as e:
            logger.error(f"Error disconnecting providers: {e}")

    def get_http_web3(self) -> AsyncWeb3:
        """
        Get HTTP Web3 instance.

        Returns:
            AsyncWeb3 instance

        Raises:
            RuntimeError: If HTTP provider not connected
        """
        if not self._http_connected or not self._http_web3:
            raise RuntimeError(
                "HTTP provider not connected. Call connect() first."
            )

        return self._http_web3

    def get_ws_web3(self) -> AsyncWeb3 | None:
        """
        Get WebSocket Web3 instance.

        Returns:
            AsyncWeb3 instance or None if not connected
        """
        if not self._ws_connected or not self._ws_web3:
            return None

        return self._ws_web3

    @property
    def is_http_connected(self) -> bool:
        """Check if HTTP provider is connected."""
        return self._http_connected

    @property
    def is_ws_connected(self) -> bool:
        """Check if WebSocket provider is connected."""
        return self._ws_connected

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on providers.

        Returns:
            Dict with health status
        """
        http_healthy = False
        ws_healthy = False
        current_block = None

        # Check HTTP
        try:
            if self._http_web3:
                current_block = await self._http_web3.eth.block_number
                http_healthy = True

        except Exception as e:
            logger.error(f"HTTP health check failed: {e}")

        # Check WebSocket
        try:
            if self._ws_web3:
                await self._ws_web3.eth.block_number
                ws_healthy = True

        except Exception as e:
            logger.warning(f"WebSocket health check failed: {e}")

        return {
            "http_connected": http_healthy,
            "ws_connected": ws_healthy,
            "current_block": current_block,
            "chain_id": self.chain_id,
        }

    async def check_node_health(self) -> bool:
        """
        Check if blockchain node is healthy (R7-5).

        Returns:
            True if node is healthy
        """
        try:
            if self._http_web3:
                # Try to get block number
                await self._http_web3.eth.block_number
                return True
        except Exception:
            pass

        return False