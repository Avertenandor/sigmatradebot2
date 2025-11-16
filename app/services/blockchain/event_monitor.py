"""
Event Monitor for USDT Transfer events.

Monitors blockchain for incoming USDT transfers to system wallet.
"""

import asyncio
from collections.abc import Callable
from decimal import Decimal

from loguru import logger
from web3 import AsyncWeb3

from .constants import USDT_ABI, USDT_DECIMALS


class EventMonitor:
    """
    Monitors USDT Transfer events on BSC blockchain.

    Uses polling mechanism to detect incoming transfers to monitored addresses.
    """

    def __init__(
        self,
        web3: AsyncWeb3,
        usdt_contract_address: str,
        poll_interval: int = 3,
    ) -> None:
        """
        Initialize event monitor.

        Args:
            web3: AsyncWeb3 instance
            usdt_contract_address: USDT contract address
            poll_interval: Polling interval in seconds
        """
        self.web3 = web3
        self.usdt_contract_address = web3.to_checksum_address(
            usdt_contract_address
        )
        self.poll_interval = poll_interval

        # Create contract instance
        self.usdt_contract = self.web3.eth.contract(
            address=self.usdt_contract_address,
            abi=USDT_ABI,
        )

        # Monitoring state
        self._monitoring = False
        self._last_processed_block = 0
        self._event_callback: Callable | None = None

        logger.info(
            f"EventMonitor initialized for USDT contract: "
            f"{self.usdt_contract_address}"
        )

    async def start_monitoring(
        self,
        watch_address: str,
        from_block: int | str = "latest",
        event_callback: Callable | None = None,
    ) -> None:
        """
        Start monitoring USDT transfers to address.

        Args:
            watch_address: Address to monitor for incoming transfers
            from_block: Starting block number or 'latest'
            event_callback: Async callback function for new transfers
        """
        self._monitoring = True
        self._event_callback = event_callback

        watch_address_checksum = self.web3.to_checksum_address(watch_address)

        # Get starting block
        if from_block == "latest":
            self._last_processed_block = await self.web3.eth.block_number
        else:
            self._last_processed_block = int(from_block)

        logger.info(
            f"Started monitoring USDT transfers to {watch_address_checksum} "
            f"from block {self._last_processed_block}"
        )

        # Start polling loop
        while self._monitoring:
            try:
                await self._poll_events(watch_address_checksum)
                await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.poll_interval * 2)

    async def _poll_events(self, watch_address: str) -> None:
        """
        Poll for new Transfer events.

        Args:
            watch_address: Address to watch
        """
        try:
            # Get current block
            current_block = await self.web3.eth.block_number

            if current_block <= self._last_processed_block:
                return  # No new blocks

            # Get Transfer events filter
            # Filter transfers TO the watch address
            event_filter = (
                await self.usdt_contract.events.Transfer.create_filter(
                    from_block=self._last_processed_block + 1,
                    to_block=current_block,
                    argument_filters={"to": watch_address},
                )
            )

            # Get all events
            events = await event_filter.get_all_entries()

            # Process each event
            for event in events:
                await self._process_event(event)

            # Update last processed block
            self._last_processed_block = current_block

        except Exception as e:
            logger.error(f"Error polling events: {e}")

    async def _process_event(self, event: any) -> None:
        """
        Process a single Transfer event.

        Args:
            event: Web3 event object
        """
        try:
            # Extract event data
            from_address = event["args"]["from"]
            to_address = event["args"]["to"]
            value_wei = event["args"]["value"]

            # Convert to USDT (18 decimals)
            amount_usdt = Decimal(value_wei) / Decimal(10**USDT_DECIMALS)

            tx_hash = event["transactionHash"].hex()
            block_number = event["blockNumber"]

            logger.info(
                f"Detected USDT transfer: {amount_usdt} USDT\n"
                f"  From: {from_address}\n"
                f"  To: {to_address}\n"
                f"  TX: {tx_hash}\n"
                f"  Block: {block_number}"
            )

            # Call event callback if provided
            if self._event_callback:
                await self._event_callback(
                    {
                        "from_address": from_address,
                        "to_address": to_address,
                        "amount": float(amount_usdt),
                        "tx_hash": tx_hash,
                        "block_number": block_number,
                    }
                )

        except Exception as e:
            logger.error(f"Error processing event: {e}")

    async def stop_monitoring(self) -> None:
        """Stop event monitoring."""
        self._monitoring = False
        logger.info("Event monitoring stopped")

    @property
    def is_monitoring(self) -> bool:
        """Check if monitoring is active."""
        return self._monitoring
