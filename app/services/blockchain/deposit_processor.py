"""
Deposit Processor.

Processes and confirms deposit transactions.
"""

from decimal import Decimal
from typing import Any

from loguru import logger
from web3 import AsyncWeb3
from web3.exceptions import TransactionNotFound

from .constants import DEFAULT_CONFIRMATION_BLOCKS, USDT_ABI, USDT_DECIMALS


class DepositProcessor:
    """
    Processes deposit transactions and checks confirmations.

    Validates:
    - Transaction exists
    - Sufficient confirmations
    - Correct recipient
    - Correct amount
    """

    def __init__(
        self,
        web3: AsyncWeb3,
        usdt_contract_address: str,
        confirmation_blocks: int = DEFAULT_CONFIRMATION_BLOCKS,
    ) -> None:
        """
        Initialize deposit processor.

        Args:
            web3: AsyncWeb3 instance
            usdt_contract_address: USDT contract address
            confirmation_blocks: Required number of confirmations
        """
        self.web3 = web3
        self.usdt_contract_address = web3.to_checksum_address(
            usdt_contract_address
        )
        self.confirmation_blocks = confirmation_blocks

        # Create contract instance
        self.usdt_contract = self.web3.eth.contract(
            address=self.usdt_contract_address,
            abi=USDT_ABI,
        )

        logger.info(
            f"DepositProcessor initialized "
            f"(confirmations required: {confirmation_blocks})"
        )

    async def check_transaction(
        self,
        tx_hash: str,
        expected_to_address: str,
        expected_amount: Decimal | None = None,
        tolerance_percent: float = 0.05,
    ) -> dict[str, Any]:
        """
        Check deposit transaction status.

        Args:
            tx_hash: Transaction hash
            expected_to_address: Expected recipient address
            expected_amount: Expected amount (optional)
            tolerance_percent: Amount tolerance (default 5%)

        Returns:
            Dict with status, confirmations, amount, etc.
        """
        try:
            # Get transaction
            tx = await self.web3.eth.get_transaction(tx_hash)

            if not tx:
                return {
                    "valid": False,
                    "error": "Transaction not found",
                    "confirmations": 0,
                }

            # Get transaction receipt
            receipt = await self.web3.eth.get_transaction_receipt(tx_hash)

            if not receipt:
                return {
                    "valid": False,
                    "error": "Transaction not mined yet",
                    "confirmations": 0,
                }

            # Check transaction success
            if receipt["status"] != 1:
                return {
                    "valid": False,
                    "error": "Transaction failed",
                    "confirmations": 0,
                }

            # Calculate confirmations
            current_block = await self.web3.eth.block_number
            tx_block = receipt["blockNumber"]
            confirmations = current_block - tx_block + 1

            # Parse Transfer event from logs
            transfer_data = self._parse_transfer_logs(
                receipt["logs"]
            )

            if not transfer_data:
                return {
                    "valid": False,
                    "error": "No USDT transfer found in transaction",
                    "confirmations": confirmations,
                }

            # Verify recipient
            if transfer_data["to"].lower() != expected_to_address.lower():
                return {
                    "valid": False,
                    "error": f"Wrong recipient: {transfer_data['to']}",
                    "confirmations": confirmations,
                }

            # R18-1: Dust attack protection - check minimum deposit amount
            from app.config.settings import settings
            actual_amount = transfer_data["amount"]
            min_deposit = Decimal(str(settings.minimum_deposit_amount))
            
            if actual_amount < min_deposit:
                logger.warning(
                    f"Dust attack detected in transaction {tx_hash}: "
                    f"amount {actual_amount} < minimum {min_deposit}"
                )
                return {
                    "valid": False,
                    "error": (
                        f"Dust attack: amount {actual_amount} is below "
                        f"minimum {min_deposit} USDT"
                    ),
                    "confirmations": confirmations,
                    "amount": actual_amount,
                }

            # Verify amount (if provided)
            if expected_amount is not None:
                min_amount = expected_amount * Decimal(1 - tolerance_percent)
                max_amount = expected_amount * Decimal(1 + tolerance_percent)

                if not (min_amount <= actual_amount <= max_amount):
                    return {
                        "valid": False,
                        "error": (
                            f"Amount mismatch: expected {expected_amount}, "
                            f"got {actual_amount}"
                        ),
                        "confirmations": confirmations,
                        "amount": actual_amount,
                    }

            # Check if enough confirmations
            is_confirmed = confirmations >= self.confirmation_blocks

            return {
                "valid": True,
                "confirmed": is_confirmed,
                "confirmations": confirmations,
                "required_confirmations": self.confirmation_blocks,
                "from_address": transfer_data["from"],
                "to_address": transfer_data["to"],
                "amount": actual_amount,
                "block_number": tx_block,
                "tx_hash": tx_hash,
            }

        except TransactionNotFound:
            return {
                "valid": False,
                "error": "Transaction not found",
                "confirmations": 0,
            }

        except Exception as e:
            logger.error(f"Error checking transaction {tx_hash}: {e}")
            return {
                "valid": False,
                "error": str(e),
                "confirmations": 0,
            }

    def _parse_transfer_logs(
        self, logs: list
    ) -> dict[str, Any] | None:
        """
        Parse Transfer event from transaction logs.

        Args:
            logs: Transaction logs

        Returns:
            Dict with from, to, amount or None
        """
        try:
            # Transfer event topic
            transfer_topic = self.web3.keccak(
                text="Transfer(address,address,uint256)"
            )

            for log in logs:
                # Check if this is a Transfer event from USDT contract
                if (
                    log["address"].lower() ==
                    self.usdt_contract_address.lower()
                    and len(log["topics"]) >= 3
                    and log["topics"][0] == transfer_topic
                ):
                    # Decode event
                    from_address = "0x" + log["topics"][1].hex()[-40:]
                    to_address = "0x" + log["topics"][2].hex()[-40:]
                    amount_wei = int(log["data"].hex(), 16)

                    amount_usdt = (
                        Decimal(amount_wei) / Decimal(10**USDT_DECIMALS)
                    )

                    return {
                        "from": self.web3.to_checksum_address(from_address),
                        "to": self.web3.to_checksum_address(to_address),
                        "amount": amount_usdt,
                    }

        except Exception as e:
            logger.error(f"Error parsing transfer logs: {e}")

        return None

    async def get_confirmations(self, tx_hash: str) -> int:
        """
        Get number of confirmations for transaction.

        Args:
            tx_hash: Transaction hash

        Returns:
            Number of confirmations
        """
        try:
            receipt = await self.web3.eth.get_transaction_receipt(tx_hash)

            if not receipt:
                return 0

            current_block = await self.web3.eth.block_number
            tx_block = receipt["blockNumber"]

            return current_block - tx_block + 1

        except Exception as e:
            logger.error(f"Error getting confirmations for {tx_hash}: {e}")
            return 0
