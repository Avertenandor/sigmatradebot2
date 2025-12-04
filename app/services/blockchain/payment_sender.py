"""
Payment Sender.

Handles USDT payment sending with gas estimation and error handling.
"""

import asyncio
from decimal import Decimal
from typing import Any

from eth_account import Account
from loguru import logger
from web3 import AsyncWeb3
from web3.exceptions import ContractLogicError

from .constants import (
    DEFAULT_GAS_LIMIT,
    MAX_GAS_PRICE_GWEI,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    USDT_ABI,
    USDT_DECIMALS,
)


class PaymentSender:
    """
    Handles USDT payment sending on BSC.

    Features:
    - Gas estimation
    - Nonce management
    - Retry with exponential backoff
    - Transaction tracking
    """

    def __init__(
        self,
        web3: AsyncWeb3,
        usdt_contract_address: str,
        payout_wallet_private_key: str | None = None,
    ) -> None:
        """
        Initialize payment sender.

        Args:
            web3: AsyncWeb3 instance
            usdt_contract_address: USDT contract address
            payout_wallet_private_key: Private key for signing transactions
        """
        self.web3 = web3
        self.usdt_contract_address = web3.to_checksum_address(
            usdt_contract_address
        )

        # Create contract instance
        self.usdt_contract = self.web3.eth.contract(
            address=self.usdt_contract_address,
            abi=USDT_ABI,
        )

        # Wallet setup
        self._private_key = payout_wallet_private_key
        self._payout_address: str | None = None
        self._account: Account | None = None

        if self._private_key:
            # Derive address from private key (cache account for reuse)
            self._account = Account.from_key(self._private_key)
            self._payout_address = self._account.address
            logger.info(
                f"PaymentSender initialized with wallet: "
                f"{self._payout_address}"
            )
        else:
            logger.warning(
                "PaymentSender initialized without private key - "
                "sending will not work"
            )

    async def send_payment(
        self,
        to_address: str,
        amount_usdt: Decimal,
        max_retries: int = MAX_RETRIES,
    ) -> dict[str, Any]:
        """
        Send USDT payment.

        Args:
            to_address: Recipient address
            amount_usdt: Amount in USDT
            max_retries: Maximum retry attempts

        Returns:
            Dict with success, tx_hash, error
        """
        if not self._private_key:
            return {
                "success": False,
                "tx_hash": None,
                "error": "Private key not configured",
            }

        # Validate and checksum address
        try:
            to_address_checksum = self.web3.to_checksum_address(to_address)
        except Exception as e:
            return {
                "success": False,
                "tx_hash": None,
                "error": f"Invalid address: {e}",
            }

        # Convert amount to wei (18 decimals for BSC USDT)
        amount_wei = int(amount_usdt * Decimal(10**USDT_DECIMALS))

        logger.info(
            f"Sending {amount_usdt} USDT to {to_address_checksum}\n"
            f"  From: {self._payout_address}\n"
            f"  Amount (wei): {amount_wei}"
        )

        # Retry logic
        for attempt in range(max_retries):
            try:
                result = await self._send_transaction(
                    to_address_checksum,
                    amount_wei,
                )

                if result["success"]:
                    logger.success(
                        f"Payment sent successfully!\n"
                        f"  TX: {result['tx_hash']}\n"
                        f"  Amount: {amount_usdt} USDT"
                    )
                    return result

                # If failed, retry
                if attempt < max_retries - 1:
                    delay = RETRY_DELAY_BASE ** (attempt + 1)
                    logger.warning(
                        f"Payment attempt {attempt + 1} failed, "
                        f"retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"Payment attempt {attempt + 1} error: {e}")

                if attempt < max_retries - 1:
                    delay = RETRY_DELAY_BASE ** (attempt + 1)
                    await asyncio.sleep(delay)

        return {
            "success": False,
            "tx_hash": None,
            "error": f"Failed after {max_retries} attempts",
        }

    async def _send_transaction(
        self,
        to_address: str,
        amount_wei: int,
    ) -> dict[str, Any]:
        """
        Send a single USDT transaction.

        Args:
            to_address: Recipient address (checksummed)
            amount_wei: Amount in wei

        Returns:
            Dict with success, tx_hash, error
        """
        try:
            # Get nonce (using 'latest' to avoid race conditions)
            # TODO: Add NonceManager with distributed lock for multi-process environments
            nonce = await self.web3.eth.get_transaction_count(
                self._payout_address, 'latest'
            )

            # Build transaction
            transfer_function = self.usdt_contract.functions.transfer(
                to_address,
                amount_wei,
            )

            # Estimate gas
            try:
                gas_estimate = await transfer_function.estimate_gas(
                    {"from": self._payout_address}
                )
                # Add 20% buffer
                gas_limit = int(gas_estimate * 1.2)
            except ContractLogicError as e:
                logger.error(f"Gas estimation failed: {e}")
                gas_limit = DEFAULT_GAS_LIMIT

            # Get gas price
            gas_price_wei = await self.web3.eth.gas_price

            # Cap gas price
            max_gas_price = self.web3.to_wei(MAX_GAS_PRICE_GWEI, "gwei")
            if gas_price_wei > max_gas_price:
                logger.warning(
                    f"Gas price {gas_price_wei} exceeds max {max_gas_price}, "
                    f"using max"
                )
                gas_price_wei = max_gas_price

            # Build transaction dict
            transaction = await transfer_function.build_transaction(
                {
                    "from": self._payout_address,
                    "gas": gas_limit,
                    "gasPrice": gas_price_wei,
                    "nonce": nonce,
                }
            )

            # Sign transaction (reuse cached account)
            signed_tx = self._account.sign_transaction(transaction)

            # Send transaction
            tx_hash = await self.web3.eth.send_raw_transaction(
                signed_tx.rawTransaction
            )

            tx_hash_hex = tx_hash.hex()

            logger.info(
                f"Transaction sent! Hash: {tx_hash_hex}\n"
                f"  Gas: {gas_limit}\n"
                f"  Gas Price: "
                f"{self.web3.from_wei(gas_price_wei, 'gwei')} Gwei"
            )

            # Wait for receipt (with timeout)
            try:
                receipt = await asyncio.wait_for(
                    self.web3.eth.wait_for_transaction_receipt(tx_hash),
                    timeout=120,  # 2 minutes
                )

                if receipt["status"] == 1:
                    return {
                        "success": True,
                        "tx_hash": tx_hash_hex,
                        "block_number": receipt["blockNumber"],
                        "gas_used": receipt["gasUsed"],
                    }
                else:
                    return {
                        "success": False,
                        "tx_hash": tx_hash_hex,
                        "error": "Transaction reverted",
                    }

            except TimeoutError:
                logger.warning(
                    f"Transaction confirmation timeout for {tx_hash_hex}. "
                    "Transaction may still be pending on blockchain."
                )
                return {
                    "success": False,
                    "tx_hash": tx_hash_hex,
                    "error": "Transaction confirmation timeout (may still be pending)",
                }

        except Exception as e:
            logger.error(f"Error sending transaction: {e}")
            return {
                "success": False,
                "tx_hash": None,
                "error": str(e),
            }

    async def estimate_gas_cost(
        self,
        to_address: str,
        amount_usdt: Decimal,
    ) -> dict[str, Any] | None:
        """
        Estimate gas cost for USDT transfer.

        Args:
            to_address: Recipient address
            amount_usdt: Amount in USDT

        Returns:
            Dict with gas_limit, gas_price, total_cost_bnb
        """
        try:
            to_address_checksum = self.web3.to_checksum_address(to_address)
            amount_wei = int(amount_usdt * Decimal(10**USDT_DECIMALS))

            # Estimate gas
            transfer_function = self.usdt_contract.functions.transfer(
                to_address_checksum,
                amount_wei,
            )

            gas_estimate = await transfer_function.estimate_gas(
                {"from": self._payout_address}
            )

            # Get gas price
            gas_price_wei = await self.web3.eth.gas_price

            # Calculate total cost in BNB
            total_cost_wei = gas_estimate * gas_price_wei
            total_cost_bnb = self.web3.from_wei(total_cost_wei, "ether")

            return {
                "gas_limit": gas_estimate,
                "gas_price_gwei": float(
                    self.web3.from_wei(gas_price_wei, "gwei")
                ),
                "total_cost_bnb": float(total_cost_bnb),
            }

        except Exception as e:
            logger.error(f"Error estimating gas: {e}")
            return None

    async def get_usdt_balance(
        self,
        address: str | None = None,
    ) -> Decimal | None:
        """
        Get USDT balance for address.

        Args:
            address: Wallet address (or payout wallet if None)

        Returns:
            USDT balance or None
        """
        try:
            check_address = address or self._payout_address
            if not check_address:
                return None

            check_address_checksum = self.web3.to_checksum_address(
                check_address
            )

            balance_wei = await self.usdt_contract.functions.balanceOf(
                check_address_checksum
            ).call()

            balance_usdt = Decimal(balance_wei) / Decimal(10**USDT_DECIMALS)

            return balance_usdt

        except Exception as e:
            logger.error(f"Error getting USDT balance: {e}")
            return None

    async def get_bnb_balance(
        self,
        address: str | None = None,
    ) -> Decimal | None:
        """
        Get BNB balance for address (for gas fees).

        Args:
            address: Wallet address (or payout wallet if None)

        Returns:
            BNB balance or None
        """
        try:
            check_address = address or self._payout_address
            if not check_address:
                return None

            check_address_checksum = self.web3.to_checksum_address(
                check_address
            )

            balance_wei = await self.web3.eth.get_balance(
                check_address_checksum
            )

            balance_bnb = Decimal(
                str(self.web3.from_wei(balance_wei, "ether"))
            )

            return balance_bnb

        except Exception as e:
            logger.error(f"Error getting BNB balance: {e}")
            return None
