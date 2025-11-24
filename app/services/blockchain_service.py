"""
Blockchain service.

Full Web3.py implementation for BSC blockchain operations
(USDT transfers, monitoring).
"""

import asyncio
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from typing import Any

# Suppress eth_utils network warnings about invalid ChainId
# These warnings are from eth_utils library initialization and don't affect functionality
# Must be set BEFORE importing eth_utils to catch warnings during module initialization
warnings.filterwarnings(
    "ignore",
    message=".*does not have a valid ChainId.*",
    category=UserWarning,
    module="eth_utils.network",
)
# Also suppress warnings from web3 which may import eth_utils
warnings.filterwarnings(
    "ignore",
    message=".*does not have a valid ChainId.*",
    category=UserWarning,
)

from eth_account import Account
from eth_utils import is_address, to_checksum_address
from loguru import logger
from web3 import Web3
from web3.middleware import geth_poa_middleware

# USDT contract ABI (ERC-20 standard functions)
USDT_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
]

# USDT decimals (BEP-20 USDT uses 18 decimals)
USDT_DECIMALS = 18


class BlockchainService:
    """
    Blockchain service for BSC/USDT operations.

    Full Web3.py implementation with:
    - USDT contract interaction
    - Transaction sending
    - Balance checking
    - Event monitoring
    - Transaction status checking
    """

    def __init__(
        self,
        rpc_url: str,
        usdt_contract: str,
        wallet_private_key: str | None,
        max_concurrent_rpc: int = 10,
        max_rps: int = 25,
    ) -> None:
        """
        Initialize blockchain service.

        Args:
            rpc_url: BSC RPC endpoint URL
            usdt_contract: USDT token contract address
            wallet_private_key: Hot wallet private key for sending payments
            max_concurrent_rpc: Maximum concurrent RPC requests (default: 10)
            max_rps: Maximum requests per second (default: 25 for $49 plan)
        """
        self.rpc_url = rpc_url
        self.usdt_contract_address = to_checksum_address(usdt_contract)
        self.wallet_private_key = wallet_private_key

        # Initialize RPC rate limiter
        from app.services.blockchain.rpc_rate_limiter import RPCRateLimiter

        self.rpc_limiter = RPCRateLimiter(
            max_concurrent=max_concurrent_rpc, max_rps=max_rps
        )

        # Thread pool executor for running synchronous Web3 calls
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="web3"
        )

        # Initialize Web3 connection
        try:
            self.web3 = Web3(Web3.HTTPProvider(rpc_url))
            # Add POA middleware for BSC
            self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)

            # Verify connection
            if not self.web3.is_connected():
                raise ConnectionError("Failed to connect to BSC RPC endpoint")

            # Get wallet address from private key (if provided)
            if wallet_private_key:
                self.wallet_account = Account.from_key(wallet_private_key)
                self.wallet_address = to_checksum_address(
                    self.wallet_account.address
                )
            else:
                self.wallet_account = None
                self.wallet_address = None
                logger.warning(
                    "BlockchainService initialized without wallet private key. "
                    "Sending payments will not be available. "
                    "Set key via /wallet_menu in bot interface."
                )

            # Initialize USDT contract
            self.usdt_contract = self.web3.eth.contract(
                address=self.usdt_contract_address, abi=USDT_ABI
            )

            wallet_info = f"  Wallet: {self.wallet_address}" if self.wallet_address else "  Wallet: Not configured"
            logger.success(
                f"BlockchainService initialized successfully\n"
                f"  RPC: {rpc_url}\n"
                f"  USDT Contract: {self.usdt_contract_address}\n"
                f"{wallet_info}\n"
                f"  Chain ID: {self.web3.eth.chain_id}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize BlockchainService: {e}")
            # Cleanup executor if initialization fails
            if hasattr(self, '_executor'):
                self._executor.shutdown(wait=True)
            raise

    def get_rpc_stats(self) -> dict[str, Any]:
        """
        Get RPC usage statistics.

        Returns:
            Dict with:
            - requests_last_minute: int
            - avg_response_time_ms: float
            - error_count: int
            - total_requests: int
        """
        return self.rpc_limiter.get_stats()

    def __del__(self) -> None:
        """
        Cleanup ThreadPoolExecutor on garbage collection.

        This ensures resources are properly released
        even if close() is not called.
        """
        if hasattr(self, '_executor') and self._executor:
            try:
                # Don't wait in __del__ to avoid blocking
                self._executor.shutdown(wait=False)
            except Exception:
                pass  # Ignore errors during cleanup

    def close(self) -> None:
        """
        Explicitly close ThreadPoolExecutor and release resources.

        Should be called when BlockchainService is no longer needed.
        """
        if hasattr(self, '_executor') and self._executor:
            logger.debug("Shutting down BlockchainService ThreadPoolExecutor")
            self._executor.shutdown(wait=True)
            self._executor = None

    async def send_payment(
        self, to_address: str, amount: float
    ) -> dict[str, Any]:
        """
        Send USDT payment.

        Args:
            to_address: Recipient wallet address (must be validated)
            amount: Amount in USDT (will be converted to wei/units)

        Returns:
            Dict with:
                - success: bool
                - tx_hash: str | None
                - error: str | None
        """
        try:
            # Check if wallet is configured
            if not self.wallet_account or not self.wallet_address:
                return {
                    "success": False,
                    "tx_hash": None,
                    "error": "Wallet private key is not configured. Set key via /wallet_menu in bot interface.",
                }
            
            # Validate recipient address
            if not await self.validate_wallet_address(to_address):
                return {
                    "success": False,
                    "tx_hash": None,
                    "error": f"Invalid recipient address: {to_address}",
                }

            # Convert to checksum address
            to_address = to_checksum_address(to_address)

            # Convert USDT amount to wei (USDT has 18 decimals)
            amount_wei = int(amount * (10 ** USDT_DECIMALS))

            # Build transfer transaction
            transfer_function = self.usdt_contract.functions.transfer(
                to_address, amount_wei
            )

            # Run synchronous Web3 calls in thread pool
            loop = asyncio.get_event_loop()

            # Get current gas price (with rate limiting)
            async with self.rpc_limiter:
                gas_price = await loop.run_in_executor(
                    self._executor, lambda: self.web3.eth.gas_price
                )

            # Estimate gas (with rate limiting)
            try:
                async with self.rpc_limiter:
                    gas_estimate = await loop.run_in_executor(
                        self._executor,
                        lambda: transfer_function.estimate_gas(
                            {"from": self.wallet_address}
                        ),
                    )
            except Exception as e:
                logger.error(f"Gas estimation failed: {e}")
                self.rpc_limiter.record_error()
                return {
                    "success": False,
                    "tx_hash": None,
                    "error": f"Gas estimation failed: {str(e)}",
                }

            # Get nonce (with rate limiting)
            async with self.rpc_limiter:
                nonce = await loop.run_in_executor(
                    self._executor,
                    lambda: self.web3.eth.get_transaction_count(
                        self.wallet_address
                    ),
                )

            # Build transaction
            transaction = transfer_function.build_transaction(
                {
                    "from": self.wallet_address,
                    "gas": int(gas_estimate * 1.2),  # Add 20% buffer
                    "gasPrice": gas_price,
                    "nonce": nonce,
                }
            )

            # Sign transaction
            signed_txn = self.wallet_account.sign_transaction(transaction)

            # Send transaction (with rate limiting)
            async with self.rpc_limiter:
                tx_hash = await loop.run_in_executor(
                    self._executor,
                    lambda: self.web3.eth.send_raw_transaction(
                        signed_txn.rawTransaction
                    ),
                )

            # Convert bytes to hex string if needed
            tx_hash_str = (
                tx_hash.hex() if isinstance(tx_hash, bytes)
                else str(tx_hash)
            )

            logger.info(
                f"USDT payment sent: {amount} USDT to {to_address}, "
                f"tx_hash: {tx_hash_str}"
            )

            return {
                "success": True,
                "tx_hash": tx_hash_str,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Failed to send USDT payment: {e}")
            return {
                "success": False,
                "tx_hash": None,
                "error": str(e),
            }

    async def check_transaction_status(
        self, tx_hash: str
    ) -> dict[str, Any]:
        """
        Check transaction status on blockchain.

        Args:
            tx_hash: Transaction hash (0x... format)

        Returns:
            Dict with:
                - status: str ("pending", "confirmed", "failed", "unknown")
                - confirmations: int (number of block confirmations)
                - block_number: int | None
                  (block number where transaction was mined)
        """
        try:
            # Validate tx_hash format
            if (
                not tx_hash or not tx_hash.startswith("0x")
                or len(tx_hash) != 66
            ):
                return {
                    "status": "invalid",
                    "confirmations": 0,
                    "block_number": None,
                }

            # Run synchronous Web3 calls in thread pool
            loop = asyncio.get_event_loop()

            # Get transaction receipt (with rate limiting)
            try:
                async with self.rpc_limiter:
                    receipt = await loop.run_in_executor(
                        self._executor,
                        lambda: self.web3.eth.get_transaction_receipt(tx_hash),
                    )
            except Exception as e:
                # Transaction not found or not yet mined
                self.rpc_limiter.record_error()
                return {
                    "status": "pending",
                    "confirmations": 0,
                    "block_number": None,
                }

            # Get current block number (with rate limiting)
            async with self.rpc_limiter:
                current_block = await loop.run_in_executor(
                    self._executor, lambda: self.web3.eth.block_number
                )

            # Calculate confirmations
            confirmations = max(0, current_block - receipt.blockNumber)

            # Determine status
            if receipt.status == 1:
                status = "confirmed"
            else:
                status = "failed"

            return {
                "status": status,
                "confirmations": confirmations,
                "block_number": receipt.blockNumber,
            }

        except Exception as e:
            logger.error(f"Failed to check transaction status: {e}")
            return {
                "status": "unknown",
                "confirmations": 0,
                "block_number": None,
            }

    async def get_transaction_details(
        self, tx_hash: str
    ) -> dict[str, Any] | None:
        """
        Get transaction details.

        Args:
            tx_hash: Transaction hash

        Returns:
            Dict with transaction details or None if not found
        """
        try:
            # Validate tx_hash
            if (
                not tx_hash or not tx_hash.startswith("0x")
                or len(tx_hash) != 66
            ):
                return None

            # Run synchronous Web3 calls in thread pool
            loop = asyncio.get_event_loop()

            # Get transaction (with rate limiting)
            try:
                async with self.rpc_limiter:
                    tx = await loop.run_in_executor(
                        self._executor,
                        lambda: self.web3.eth.get_transaction(tx_hash)
                    )
            except Exception as e:
                self.rpc_limiter.record_error()
                return None

            # Get receipt (with rate limiting)
            try:
                async with self.rpc_limiter:
                    receipt = await loop.run_in_executor(
                        self._executor,
                        lambda: self.web3.eth.get_transaction_receipt(tx_hash),
                    )
            except Exception:
                receipt = None

            # Get current block (with rate limiting)
            async with self.rpc_limiter:
                current_block = await loop.run_in_executor(
                    self._executor, lambda: self.web3.eth.block_number
                )

            # Parse transaction data for USDT transfer
            from_address = to_checksum_address(tx["from"])
            to_address = to_checksum_address(tx["to"]) if tx["to"] else None

            # Check if this is a USDT contract call
            value = Decimal(0)
            if (
                to_address and
                to_address.lower() == self.usdt_contract_address.lower()
            ):
                # Decode contract call data
                try:
                    decoded = self.usdt_contract.decode_function_input(
                        tx["input"]
                    )
                    if decoded[0].fn_name == "transfer":
                        # Extract amount from transfer function
                        amount_wei = decoded[1]["_value"]
                        value = (
                            Decimal(amount_wei) /
                            Decimal(10 ** USDT_DECIMALS)
                        )
                        # Update to_address to actual recipient
                        to_address = to_checksum_address(decoded[1]["_to"])
                except Exception as e:
                    logger.warning(f"Failed to decode USDT transfer: {e}")

            # Calculate confirmations
            confirmations = 0
            if receipt:
                confirmations = max(0, current_block - receipt.blockNumber)

            return {
                "from_address": from_address,
                "to_address": to_address,
                "value": value,
                "gas_used": receipt.gasUsed if receipt else None,
                "gas_price": tx.gasPrice,
                "block_number": receipt.blockNumber if receipt else None,
                "confirmations": confirmations,
                "status": (
                    "confirmed" if receipt and receipt.status == 1
                    else "pending"
                ),
            }

        except Exception as e:
            logger.error(f"Failed to get transaction details: {e}")
            return None

    async def validate_wallet_address(
        self, address: str
    ) -> bool:
        """
        Validate BSC wallet address format and checksum.

        Args:
            address: Wallet address

        Returns:
            True if valid
        """
        try:
            if not address or not isinstance(address, str):
                return False

            # Check if valid address format
            if not is_address(address):
                return False

            # Convert to checksum address (validates checksum)
            to_checksum_address(address)
            return True

        except Exception:
            return False

    def validate_wallet_address_sync(
        self, address: str
    ) -> bool:
        """
        Synchronous version of validate_wallet_address.

        Args:
            address: Wallet address

        Returns:
            True if valid
        """
        try:
            if not address or not isinstance(address, str):
                return False

            if not is_address(address):
                return False

            to_checksum_address(address)
            return True

        except Exception:
            return False

    async def get_usdt_balance(
        self, address: str
    ) -> Decimal | None:
        """
        Get USDT balance for address.

        Args:
            address: Wallet address (must be validated)

        Returns:
            USDT balance as Decimal, or None if error
        """
        try:
            # Validate address
            if not await self.validate_wallet_address(address):
                logger.warning(f"Invalid address for balance check: {address}")
                return None

            # Convert to checksum address
            address = to_checksum_address(address)

            # Run synchronous Web3 call in thread pool (with rate limiting)
            loop = asyncio.get_event_loop()
            async with self.rpc_limiter:
                balance_wei = await loop.run_in_executor(
                    self._executor,
                    lambda: self.usdt_contract.functions.balanceOf(address).call(),
                )

            # Convert from wei to USDT
            balance = Decimal(balance_wei) / Decimal(10 ** USDT_DECIMALS)

            return balance

        except Exception as e:
            logger.error(f"Failed to get USDT balance: {e}")
            return None

    async def estimate_gas_fee(
        self, to_address: str, amount: Decimal
    ) -> Decimal | None:
        """
        Estimate gas fee for USDT transfer.

        Args:
            to_address: Recipient address (must be validated)
            amount: Transfer amount in USDT

        Returns:
            Estimated gas fee in BNB as Decimal, or None if error
        """
        try:
            # Validate address
            if not await self.validate_wallet_address(to_address):
                logger.warning(
                    f"Invalid address for gas estimation: {to_address}"
                )
                return None

            # Convert to checksum address
            to_address = to_checksum_address(to_address)

            # Convert USDT amount to wei
            amount_wei = int(amount * (10 ** USDT_DECIMALS))

            # Build transfer function
            transfer_function = self.usdt_contract.functions.transfer(
                to_address, amount_wei
            )

            # Run synchronous Web3 calls in thread pool
            loop = asyncio.get_event_loop()

            # Estimate gas (with rate limiting)
            async with self.rpc_limiter:
                gas_estimate = await loop.run_in_executor(
                    self._executor,
                    lambda: transfer_function.estimate_gas(
                        {"from": self.wallet_address}
                    ),
                )

            # Get current gas price (with rate limiting)
            async with self.rpc_limiter:
                gas_price = await loop.run_in_executor(
                    self._executor, lambda: self.web3.eth.gas_price
                )

            # Calculate total fee in wei
            total_fee_wei = gas_estimate * gas_price

            # Convert from wei to BNB (BNB also has 18 decimals)
            total_fee_bnb = Decimal(total_fee_wei) / Decimal(10 ** 18)

            return total_fee_bnb

        except Exception as e:
            logger.error(f"Failed to estimate gas fee: {e}")
            return None

    async def search_blockchain_for_deposit(
        self,
        user_wallet: str,
        expected_amount: Decimal,
        from_block: int = 0,
        to_block: int | str = "latest",
        tolerance_percent: float = 0.05,
    ) -> dict[str, Any] | None:
        """
        Search blockchain history for USDT transfer matching deposit criteria.

        R3-6: Last attempt to find transaction before marking deposit as failed.

        Args:
            user_wallet: User's wallet address (from)
            expected_amount: Expected USDT amount
            from_block: Starting block number (default: 0)
            to_block: Ending block number or 'latest' (default: 'latest')
            tolerance_percent: Amount tolerance (default: 5%)

        Returns:
            Dict with tx_hash, block_number, amount, confirmations or None if not found
        """
        try:
            # Validate address
            if not await self.validate_wallet_address(user_wallet):
                logger.warning(f"Invalid user wallet address: {user_wallet}")
                return None

            # Convert to checksum addresses
            user_wallet_checksum = to_checksum_address(user_wallet)
            system_wallet_checksum = to_checksum_address(
                self.system_wallet_address
            )

            # Calculate tolerance
            tolerance = expected_amount * Decimal(tolerance_percent)
            min_amount = expected_amount - tolerance
            max_amount = expected_amount + tolerance

            # Convert amounts to wei for comparison
            min_amount_wei = int(min_amount * Decimal(10**USDT_DECIMALS))
            max_amount_wei = int(max_amount * Decimal(10**USDT_DECIMALS))

            # Get current block if 'latest'
            loop = asyncio.get_event_loop()
            if to_block == "latest":
                async with self.rpc_limiter:
                    to_block = await loop.run_in_executor(
                        self._executor, lambda: self.web3.eth.block_number
                    )

            # Limit search to last 100k blocks (about 3 days on BSC)
            # to avoid excessive RPC calls
            max_search_blocks = 100000
            if from_block < to_block - max_search_blocks:
                from_block = to_block - max_search_blocks
                logger.info(
                    f"Limiting search to last {max_search_blocks} blocks "
                    f"(from_block={from_block}, to_block={to_block})"
                )

            # Create filter for Transfer events
            # Filter: from=user_wallet, to=system_wallet
            async with self.rpc_limiter:
                event_filter = await loop.run_in_executor(
                    self._executor,
                    lambda: self.usdt_contract.events.Transfer.create_filter(
                        fromBlock=from_block,
                        toBlock=to_block,
                        argument_filters={
                            "from": user_wallet_checksum,
                            "to": system_wallet_checksum,
                        },
                    ),
                )

            # Get all matching events
            async with self.rpc_limiter:
                events = await loop.run_in_executor(
                    self._executor, lambda: event_filter.get_all_entries()
                )

            # Find matching event by amount
            for event in events:
                value_wei = event.args["value"]
                amount_usdt = Decimal(value_wei) / Decimal(10**USDT_DECIMALS)

                # Check if amount matches (within tolerance)
                if min_amount_wei <= value_wei <= max_amount_wei:
                    # Get transaction details
                    tx_hash = (
                        event.transactionHash.hex()
                        if hasattr(event.transactionHash, "hex")
                        else str(event.transactionHash)
                    )
                    block_number = event.blockNumber

                    # Get current block for confirmations
                    async with self.rpc_limiter:
                        current_block = await loop.run_in_executor(
                            self._executor, lambda: self.web3.eth.block_number
                        )
                    confirmations = current_block - block_number

                    logger.info(
                        f"Found matching deposit transaction: "
                        f"tx_hash={tx_hash}, amount={amount_usdt}, "
                        f"block={block_number}, confirmations={confirmations}"
                    )

                    return {
                        "tx_hash": tx_hash,
                        "block_number": block_number,
                        "amount": amount_usdt,
                        "confirmations": confirmations,
                    }

            logger.debug(
                f"No matching deposit found for {user_wallet} "
                f"amount {expected_amount} in blocks {from_block}-{to_block}"
            )
            return None

        except Exception as e:
            logger.error(
                f"Error searching blockchain for deposit from {user_wallet}: {e}"
            )
            return None

    async def monitor_incoming_deposits(
        self, wallet_address: str, from_block: int
    ) -> list[dict[str, Any]]:
        """
        Monitor incoming USDT deposits to wallet.

        Args:
            wallet_address: Wallet address to monitor (must be validated)
            from_block: Starting block number for event filtering

        Returns:
            List of deposit transaction dicts
        """
        try:
            # Validate address
            if not await self.validate_wallet_address(wallet_address):
                logger.warning(
                    f"Invalid address for deposit monitoring: "
                    f"{wallet_address}"
                )
                return []

            # Convert to checksum address
            wallet_address = to_checksum_address(wallet_address)

            # Run synchronous Web3 calls in thread pool
            loop = asyncio.get_event_loop()

            # Get current block (with rate limiting)
            async with self.rpc_limiter:
                current_block = await loop.run_in_executor(
                    self._executor, lambda: self.web3.eth.block_number
                )

            # Create event filter for Transfer events (with rate limiting)
            async with self.rpc_limiter:
                event_filter = await loop.run_in_executor(
                    self._executor,
                    lambda: self.usdt_contract.events.Transfer.create_filter(
                        fromBlock=from_block,
                        toBlock=current_block,
                        argument_filters={"to": wallet_address},
                    ),
                )

            # Get all events (with rate limiting)
            async with self.rpc_limiter:
                events = await loop.run_in_executor(
                    self._executor, lambda: event_filter.get_all_entries()
                )

            # Parse events
            deposits = []
            for event in events:
                try:
                    # Get transaction details
                    tx_hash = (
                        event.transactionHash.hex()
                        if hasattr(event.transactionHash, 'hex')
                        else str(event.transactionHash)
                    )
                    tx_details = await self.get_transaction_details(tx_hash)

                    if tx_details:
                        deposits.append({
                            "tx_hash": tx_hash,
                            "from_address": to_checksum_address(
                                event.args["from"]
                            ),
                            "to_address": wallet_address,
                            "amount": (
                                Decimal(event.args["value"]) /
                                Decimal(10 ** USDT_DECIMALS)
                            ),
                            "block_number": event.blockNumber,
                            "timestamp": datetime.utcnow(),  # Approximate
                        })
                except Exception as e:
                    logger.warning(f"Failed to parse deposit event: {e}")

            logger.info(
                f"Found {len(deposits)} deposits to {wallet_address} "
                f"from block {from_block}"
            )

            return deposits

        except Exception as e:
            logger.error(f"Failed to monitor deposits: {e}")
            return []

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on blockchain service.

        Returns:
            Dict with health status
        """
        try:
            loop = asyncio.get_event_loop()
            
            # Check if we can get latest block (synchronous call in executor)
            async with self.rpc_limiter:
                latest_block = await loop.run_in_executor(
                    self._executor,
                    lambda: self.web3.eth.get_block('latest')
                )
            
            # Check USDT contract (synchronous call in executor)
            # Don't check system wallet balance if address not set
            usdt_balance = 0.0
            if hasattr(self, 'system_wallet_address') and self.system_wallet_address:
                async with self.rpc_limiter:
                    balance_wei = await loop.run_in_executor(
                        self._executor,
                        lambda: self.usdt_contract.functions.balanceOf(
                            self.system_wallet_address
                        ).call()
                    )
                usdt_balance = float(Decimal(balance_wei) / Decimal(10 ** USDT_DECIMALS))
            
            connected = True
            
            return {
                "initialized": True,
                "connected": connected,
                "providers": {
                    "http_connected": connected,
                    "ws_connected": False # WebSocket not implemented in this service class yet
                },
                "latest_block": latest_block.number,
                "usdt_balance": usdt_balance,
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "initialized": False,
                "connected": False,
                "providers": {
                    "http_connected": False,
                    "ws_connected": False
                },
                "error": str(e),
            }


# Singleton instance (to be initialized with config)
_blockchain_service: BlockchainService | None = None


def get_blockchain_service() -> BlockchainService:
    """
    Get blockchain service singleton.

    Returns:
        BlockchainService instance
    """
    global _blockchain_service

    if _blockchain_service is None:
        raise RuntimeError(
            "BlockchainService not initialized. "
            "Call init_blockchain_service() first."
        )

    return _blockchain_service


def init_blockchain_service(
    rpc_url: str,
    usdt_contract: str,
    wallet_private_key: str | None,
) -> None:
    """
    Initialize blockchain service singleton.

    Args:
        rpc_url: BSC RPC endpoint URL
        usdt_contract: USDT token contract address
        wallet_private_key: Hot wallet private key
    """
    global _blockchain_service

    _blockchain_service = BlockchainService(
        rpc_url=rpc_url,
        usdt_contract=usdt_contract,
        wallet_private_key=wallet_private_key,
        max_concurrent_rpc=10,  # Default: 10 concurrent requests
        max_rps=25,  # Default: 25 RPS for $49 QuickNode plan
    )

    logger.info("BlockchainService singleton initialized")
