"""
Blockchain Service - Main Interface.

Orchestrates all blockchain operations using component services.
"""

from collections.abc import Callable
from decimal import Decimal

from loguru import logger

from .deposit_processor import DepositProcessor
from .event_monitor import EventMonitor
from .payment_sender import PaymentSender
from .provider_manager import ProviderManager


class BlockchainService:
    """
    Main blockchain service interface.

    Orchestrates:
    - Provider management (HTTP/WebSocket)
    - Event monitoring (USDT transfers)
    - Deposit processing (confirmations)
    - Payment sending (USDT transfers)
    """

    def __init__(
        self,
        https_url: str,
        wss_url: str,
        usdt_contract_address: str,
        system_wallet_address: str,
        payout_wallet_address: str,
        payout_wallet_private_key: str | None = None,
        chain_id: int = 56,
        confirmation_blocks: int = 12,
        poll_interval: int = 3,
    ) -> None:
        """
        Initialize blockchain service.

        Args:
            https_url: QuickNode HTTPS URL
            wss_url: QuickNode WebSocket URL
            usdt_contract_address: USDT contract address
            system_wallet_address: System deposit wallet
            payout_wallet_address: Payout wallet
            payout_wallet_private_key: Private key for payouts
            chain_id: BSC chain ID (56=mainnet, 97=testnet)
            confirmation_blocks: Required confirmations
            poll_interval: Event polling interval (seconds)
        """
        self.https_url = https_url
        self.wss_url = wss_url
        self.usdt_contract_address = usdt_contract_address
        self.system_wallet_address = system_wallet_address
        self.payout_wallet_address = payout_wallet_address
        self.chain_id = chain_id
        self.confirmation_blocks = confirmation_blocks

        # Initialize provider manager
        self.provider_manager = ProviderManager(
            https_url=https_url,
            wss_url=wss_url,
            chain_id=chain_id,
        )

        # Component services (initialized after provider connection)
        self._event_monitor: EventMonitor | None = None
        self._deposit_processor: DepositProcessor | None = None
        self._payment_sender: PaymentSender | None = None

        # Store private key (will be used when initializing payment sender)
        self._payout_wallet_private_key = payout_wallet_private_key
        self._poll_interval = poll_interval

        # Connected state
        self._initialized = False

        logger.info(
            "BlockchainService initialized (not yet connected)\n"
            f"  Chain ID: {chain_id}\n"
            f"  System Wallet: {system_wallet_address}\n"
            f"  Payout Wallet: {payout_wallet_address}\n"
            f"  Confirmations: {confirmation_blocks}"
        )

    async def connect(self) -> None:
        """Connect to blockchain providers and initialize components."""
        if self._initialized:
            logger.warning("BlockchainService already initialized")
            return

        # Connect providers
        await self.provider_manager.connect()

        # Get Web3 instance
        web3 = self.provider_manager.get_http_web3()

        # Initialize components
        self._event_monitor = EventMonitor(
            web3=web3,
            usdt_contract_address=self.usdt_contract_address,
            poll_interval=self._poll_interval,
        )

        self._deposit_processor = DepositProcessor(
            web3=web3,
            usdt_contract_address=self.usdt_contract_address,
            confirmation_blocks=self.confirmation_blocks,
        )

        self._payment_sender = PaymentSender(
            web3=web3,
            usdt_contract_address=self.usdt_contract_address,
            payout_wallet_private_key=self._payout_wallet_private_key,
        )

        self._initialized = True

        logger.success("BlockchainService connected and initialized")

    async def disconnect(self) -> None:
        """Disconnect from blockchain providers."""
        # Stop event monitoring if active
        if self._event_monitor and self._event_monitor.is_monitoring:
            await self._event_monitor.stop_monitoring()

        # Disconnect providers
        await self.provider_manager.disconnect()

        self._initialized = False
        logger.info("BlockchainService disconnected")

    # === Event Monitoring ===

    async def start_deposit_monitoring(
        self,
        event_callback: Callable | None = None,
        from_block: int | str = "latest",
    ) -> None:
        """
        Start monitoring USDT deposits to system wallet.

        Args:
            event_callback: Async callback for new deposits
            from_block: Starting block number or 'latest'
        """
        self._ensure_initialized()

        await self._event_monitor.start_monitoring(
            watch_address=self.system_wallet_address,
            from_block=from_block,
            event_callback=event_callback,
        )

    async def stop_deposit_monitoring(self) -> None:
        """Stop deposit monitoring."""
        self._ensure_initialized()
        await self._event_monitor.stop_monitoring()

    # === Deposit Processing ===

    async def check_deposit_transaction(
        self,
        tx_hash: str,
        expected_amount: Decimal | None = None,
        tolerance_percent: float = 0.05,
    ) -> dict[str, any]:
        """
        Check deposit transaction status.

        Args:
            tx_hash: Transaction hash
            expected_amount: Expected USDT amount (optional)
            tolerance_percent: Amount tolerance (default 5%)

        Returns:
            Dict with valid, confirmed, confirmations, amount, etc.
        """
        self._ensure_initialized()

        return await self._deposit_processor.check_transaction(
            tx_hash=tx_hash,
            expected_to_address=self.system_wallet_address,
            expected_amount=expected_amount,
            tolerance_percent=tolerance_percent,
        )

    async def get_transaction_confirmations(self, tx_hash: str) -> int:
        """
        Get number of confirmations for transaction.

        Args:
            tx_hash: Transaction hash

        Returns:
            Number of confirmations
        """
        self._ensure_initialized()
        return await self._deposit_processor.get_confirmations(tx_hash)

    # === Payment Sending ===

    async def send_payment(
        self,
        to_address: str,
        amount_usdt: Decimal,
        max_retries: int = 5,
    ) -> dict[str, any]:
        """
        Send USDT payment.

        Args:
            to_address: Recipient wallet address
            amount_usdt: Amount in USDT
            max_retries: Maximum retry attempts

        Returns:
            Dict with success, tx_hash, error
        """
        self._ensure_initialized()

        return await self._payment_sender.send_payment(
            to_address=to_address,
            amount_usdt=amount_usdt,
            max_retries=max_retries,
        )

    async def estimate_gas_cost(
        self,
        to_address: str,
        amount_usdt: Decimal,
    ) -> dict[str, any] | None:
        """
        Estimate gas cost for payment.

        Args:
            to_address: Recipient address
            amount_usdt: Amount in USDT

        Returns:
            Dict with gas_limit, gas_price_gwei, total_cost_bnb
        """
        self._ensure_initialized()

        return await self._payment_sender.estimate_gas_cost(
            to_address=to_address,
            amount_usdt=amount_usdt,
        )

    # === Balance Queries ===

    async def get_usdt_balance(
        self,
        address: str | None = None,
    ) -> Decimal | None:
        """
        Get USDT balance for address.

        Args:
            address: Wallet address (payout wallet if None)

        Returns:
            USDT balance or None
        """
        self._ensure_initialized()
        return await self._payment_sender.get_usdt_balance(address)

    async def get_bnb_balance(
        self,
        address: str | None = None,
    ) -> Decimal | None:
        """
        Get BNB balance for address (for gas fees).

        Args:
            address: Wallet address (payout wallet if None)

        Returns:
            BNB balance or None
        """
        self._ensure_initialized()
        return await self._payment_sender.get_bnb_balance(address)

    # === Wallet Validation ===

    async def validate_wallet_address(self, address: str) -> bool:
        """
        Validate BSC wallet address format.

        Args:
            address: Wallet address

        Returns:
            True if valid
        """
        if not address or not isinstance(address, str):
            return False

        if not address.startswith("0x"):
            return False

        if len(address) != 42:  # 0x + 40 hex chars
            return False

        # Check if all chars after 0x are hex
        try:
            int(address[2:], 16)
            return True
        except ValueError:
            return False

    # === Health & Status ===

    async def health_check(self) -> dict[str, any]:
        """
        Perform health check on blockchain service.

        Returns:
            Dict with health status
        """
        if not self._initialized:
            return {
                "initialized": False,
                "providers": {},
                "balances": {},
            }

        # Check providers
        provider_health = await self.provider_manager.health_check()

        # Check balances
        try:
            payout_usdt = await self.get_usdt_balance()
            payout_bnb = await self.get_bnb_balance()
            system_usdt = await self.get_usdt_balance(
                self.system_wallet_address
            )
        except Exception as e:
            logger.error(f"Error checking balances: {e}")
            payout_usdt = None
            payout_bnb = None
            system_usdt = None

        return {
            "initialized": True,
            "providers": provider_health,
            "balances": {
                "payout_wallet": {
                    "address": self.payout_wallet_address,
                    "usdt": float(payout_usdt) if payout_usdt else None,
                    "bnb": float(payout_bnb) if payout_bnb else None,
                },
                "system_wallet": {
                    "address": self.system_wallet_address,
                    "usdt": float(system_usdt) if system_usdt else None,
                },
            },
            "monitoring_active": (
                self._event_monitor.is_monitoring
                if self._event_monitor
                else False
            ),
        }

    def _ensure_initialized(self) -> None:
        """
        Ensure service is initialized.

        Raises:
            RuntimeError: If not initialized
        """
        if not self._initialized:
            raise RuntimeError(
                "BlockchainService not initialized. Call connect() first."
            )


# === Singleton Pattern ===

_blockchain_service: BlockchainService | None = None


def get_blockchain_service() -> BlockchainService:
    """
    Get blockchain service singleton.

    Returns:
        BlockchainService instance

    Raises:
        RuntimeError: If not initialized
    """
    global _blockchain_service

    if _blockchain_service is None:
        raise RuntimeError(
            "BlockchainService not initialized. "
            "Call init_blockchain_service() first."
        )

    return _blockchain_service


def init_blockchain_service(
    https_url: str,
    wss_url: str,
    usdt_contract_address: str,
    system_wallet_address: str,
    payout_wallet_address: str,
    payout_wallet_private_key: str | None = None,
    chain_id: int = 56,
    confirmation_blocks: int = 12,
    poll_interval: int = 3,
) -> BlockchainService:
    """
    Initialize blockchain service singleton.

    Args:
        https_url: QuickNode HTTPS URL
        wss_url: QuickNode WebSocket URL
        usdt_contract_address: USDT contract address
        system_wallet_address: System deposit wallet
        payout_wallet_address: Payout wallet
        payout_wallet_private_key: Private key for payouts
        chain_id: BSC chain ID
        confirmation_blocks: Required confirmations
        poll_interval: Event polling interval

    Returns:
        BlockchainService instance
    """
    global _blockchain_service

    _blockchain_service = BlockchainService(
        https_url=https_url,
        wss_url=wss_url,
        usdt_contract_address=usdt_contract_address,
        system_wallet_address=system_wallet_address,
        payout_wallet_address=payout_wallet_address,
        payout_wallet_private_key=payout_wallet_private_key,
        chain_id=chain_id,
        confirmation_blocks=confirmation_blocks,
        poll_interval=poll_interval,
    )

    logger.info("BlockchainService singleton initialized")

    return _blockchain_service
