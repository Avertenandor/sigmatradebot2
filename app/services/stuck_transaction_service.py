"""
Stuck Transaction Service (R7-6).

Monitors and handles stuck withdrawal transactions.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web3.exceptions import TransactionNotFound

from app.models.enums import TransactionStatus, TransactionType
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.transaction_repository import TransactionRepository
from app.services.user_service import UserService


class StuckTransactionService:
    """Service for monitoring and handling stuck transactions."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize stuck transaction service."""
        self.session = session
        self.transaction_repo = TransactionRepository(session)
        self.user_service = UserService(session)

    async def find_stuck_withdrawals(
        self, older_than_minutes: int = 15
    ) -> list[Transaction]:
        """
        Find withdrawal transactions in PROCESSING status older than threshold.

        Args:
            older_than_minutes: Minimum age in minutes to consider stuck

        Returns:
            List of stuck withdrawal transactions
        """
        threshold = datetime.now(UTC) - timedelta(minutes=older_than_minutes)
        # Convert to naive datetime (UTC) to match Transaction model's naive DateTime column
        # This avoids "can't subtract offset-naive and offset-aware datetimes" error in asyncpg
        threshold_naive = threshold.replace(tzinfo=None)

        stmt = (
            select(Transaction)
            .where(
                Transaction.type == TransactionType.WITHDRAWAL.value,
                Transaction.status == TransactionStatus.PROCESSING.value,
                Transaction.tx_hash.isnot(None),
                Transaction.updated_at < threshold_naive,
            )
            .order_by(Transaction.updated_at.asc())
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def check_transaction_status(
        self, tx_hash: str, web3
    ) -> dict[str, Any]:
        """
        Check transaction status in blockchain.

        Args:
            tx_hash: Transaction hash
            web3: Web3 instance

        Returns:
            Dict with status, receipt, error
        """
        try:
            # Try to get transaction receipt
            try:
                receipt = await web3.eth.get_transaction_receipt(tx_hash)
            except TransactionNotFound:
                # Transaction not mined yet - check if it's in mempool
                try:
                    tx = await web3.eth.get_transaction(tx_hash)
                    if tx:
                        return {
                            "status": "pending",
                            "in_mempool": True,
                            "receipt": None,
                        }
                except TransactionNotFound:
                    pass

                return {
                    "status": "not_found",
                    "in_mempool": False,
                    "receipt": None,
                }

            # Transaction has receipt
            if receipt["status"] == 1:
                return {
                    "status": "confirmed",
                    "in_mempool": False,
                    "receipt": receipt,
                    "block_number": receipt["blockNumber"],
                }
            else:
                return {
                    "status": "failed",
                    "in_mempool": False,
                    "receipt": receipt,
                    "error": "Transaction reverted",
                }

        except Exception as e:
            logger.error(f"Error checking transaction {tx_hash}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "receipt": None,
            }

    async def handle_stuck_transaction(
        self,
        withdrawal: Transaction,
        tx_status: dict[str, Any],
        web3,
    ) -> dict[str, Any]:
        """
        Handle stuck transaction based on its status.

        Args:
            withdrawal: Withdrawal transaction
            tx_status: Transaction status from blockchain
            web3: Web3 instance

        Returns:
            Dict with action taken and result
        """
        status = tx_status.get("status")

        if status == "confirmed":
            # Transaction confirmed - update to CONFIRMED
            withdrawal.status = TransactionStatus.CONFIRMED.value
            await self.session.commit()

            logger.info(
                f"Stuck transaction {withdrawal.id} confirmed",
                extra={
                    "transaction_id": withdrawal.id,
                    "tx_hash": withdrawal.tx_hash,
                },
            )

            return {
                "action": "confirmed",
                "success": True,
            }

        elif status == "failed":
            # Transaction failed - return funds to user
            try:
                # Get user with lock
                stmt = (
                    select(User)
                    .where(User.id == withdrawal.user_id)
                    .with_for_update()
                )
                result = await self.session.execute(stmt)
                user = result.scalar_one_or_none()

                if user:
                    # Return balance to user
                    user.balance = user.balance + withdrawal.amount

                # Update withdrawal status
                withdrawal.status = TransactionStatus.FAILED.value

                await self.session.commit()

                logger.warning(
                    f"Stuck transaction {withdrawal.id} failed, "
                    f"funds returned to user",
                    extra={
                        "transaction_id": withdrawal.id,
                        "tx_hash": withdrawal.tx_hash,
                        "user_id": withdrawal.user_id,
                        "amount": str(withdrawal.amount),
                    },
                )

                return {
                    "action": "failed_refunded",
                    "success": True,
                }

            except Exception as e:
                await self.session.rollback()
                logger.error(
                    f"Error handling failed transaction {withdrawal.id}: {e}"
                )
                return {
                    "action": "failed_refund_error",
                    "success": False,
                    "error": str(e),
                }

        elif status == "pending":
            # Transaction pending in mempool - try speed-up
            try:
                # Get current transaction
                tx = await web3.eth.get_transaction(withdrawal.tx_hash)
                if not tx:
                    return {
                        "action": "pending_no_tx",
                        "success": False,
                    }

                # Get current gas price
                current_gas_price = await web3.eth.gas_price
                tx_gas_price = tx.get("gasPrice", 0)

                # If our gas price is lower, try speed-up
                if tx_gas_price < current_gas_price:
                    # Increase gas by 20%
                    new_gas_price = int(current_gas_price * 1.2)

                    logger.info(
                        f"Attempting speed-up for transaction "
                        f"{withdrawal.tx_hash}: "
                        f"old gas {tx_gas_price}, new gas {new_gas_price}",
                    )

                    # Note: Speed-up requires sending replacement transaction
                    # with same nonce but higher gas. This is complex and
                    # requires access to private key. For now, we just log it.
                    # In production, this should be handled by PaymentSender
                    # or a dedicated speed-up service.

                    return {
                        "action": "pending_speedup_needed",
                        "success": False,
                        "current_gas": tx_gas_price,
                        "recommended_gas": new_gas_price,
                    }

                return {
                    "action": "pending_waiting",
                    "success": False,
                }

            except Exception as e:
                logger.error(
                    f"Error checking pending transaction "
                    f"{withdrawal.tx_hash}: {e}"
                )
                return {
                    "action": "pending_check_error",
                    "success": False,
                    "error": str(e),
                }

        elif status == "not_found":
            # Transaction not found - might be dropped
            # Try to resend with new nonce
            logger.warning(
                f"Transaction {withdrawal.tx_hash} not found, "
                f"might be dropped",
                extra={
                    "transaction_id": withdrawal.id,
                    "tx_hash": withdrawal.tx_hash,
                },
            )

            return {
                "action": "not_found_retry_needed",
                "success": False,
            }

        else:
            # Error checking transaction
            logger.error(
                f"Error status for transaction {withdrawal.tx_hash}: "
                f"{tx_status.get('error')}",
            )

            return {
                "action": "error",
                "success": False,
                "error": tx_status.get("error"),
            }



