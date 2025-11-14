"""
Payment retry service (PART5 critical).

Exponential backoff retry mechanism for failed payments.
Prevents user fund loss from transient failures.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deposit_reward import DepositReward
from app.models.enums import PaymentType, TransactionStatus, TransactionType
from app.models.payment_retry import PaymentRetry
from app.models.referral_earning import ReferralEarning
from app.models.transaction import Transaction
from app.repositories.deposit_reward_repository import (
    DepositRewardRepository,
)
from app.repositories.payment_retry_repository import (
    PaymentRetryRepository,
)
from app.repositories.referral_earning_repository import (
    ReferralEarningRepository,
)
from app.repositories.transaction_repository import TransactionRepository


# Exponential backoff: 1min, 2min, 4min, 8min, 16min
BASE_RETRY_DELAY_MINUTES = 1
DEFAULT_MAX_RETRIES = 5


class PaymentRetryService:
    """Payment retry service with exponential backoff and DLQ."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize payment retry service."""
        self.session = session
        self.retry_repo = PaymentRetryRepository(session)
        self.earning_repo = ReferralEarningRepository(session)
        self.reward_repo = DepositRewardRepository(session)
        self.transaction_repo = TransactionRepository(session)

    async def create_retry_record(
        self,
        user_id: int,
        amount: Decimal,
        payment_type: PaymentType,
        earning_ids: list[int],
        error: str,
        error_stack: Optional[str] = None,
    ) -> PaymentRetry:
        """
        Create retry record for failed payment.

        Args:
            user_id: User ID
            amount: Payment amount
            payment_type: REFERRAL_EARNING or DEPOSIT_REWARD
            earning_ids: IDs of earnings/rewards to pay
            error: Error message
            error_stack: Error stack trace (optional)

        Returns:
            PaymentRetry record
        """
        logger.info(
            f"Creating retry record for user {user_id}, "
            f"amount: {amount} USDT",
            extra={
                "payment_type": payment_type.value,
                "earning_ids": earning_ids,
            },
        )

        # Check if retry already exists
        existing = await self.retry_repo.find_by(
            user_id=user_id,
            payment_type=payment_type.value,
            resolved=False,
        )

        if existing:
            # Update existing record
            retry = existing[0]
            await self.retry_repo.update(
                retry.id,
                amount=amount,
                earning_ids=earning_ids,
                last_error=error,
                error_stack=error_stack,
            )
            logger.info(
                f"Updated existing retry record {retry.id}"
            )
        else:
            # Create new retry record
            next_retry_at = self._calculate_next_retry_time(0)

            retry = await self.retry_repo.create(
                user_id=user_id,
                amount=amount,
                payment_type=payment_type.value,
                earning_ids=earning_ids,
                attempt_count=0,
                max_retries=DEFAULT_MAX_RETRIES,
                next_retry_at=next_retry_at,
                last_error=error,
                error_stack=error_stack,
                in_dlq=False,
                resolved=False,
            )

            logger.info(
                f"Created new retry record {retry.id}, "
                f"next retry at: {next_retry_at.isoformat()}"
            )

        await self.session.commit()
        return retry

    async def process_pending_retries(
        self, blockchain_service
    ) -> dict:
        """
        Process all pending retries.

        Called by background job (e.g., every minute).

        Args:
            blockchain_service: Blockchain service for sending payments

        Returns:
            Dict with processed, successful, failed, moved_to_dlq counts
        """
        # Get pending retries
        pending = await self.retry_repo.get_pending_retries()

        if not pending:
            return {
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "moved_to_dlq": 0,
            }

        logger.info(
            f"Processing {len(pending)} pending payment retries..."
        )

        processed = 0
        successful = 0
        failed = 0
        moved_to_dlq = 0

        for retry in pending:
            try:
                result = await self._process_retry(
                    retry, blockchain_service
                )
                processed += 1

                if result["success"]:
                    successful += 1
                elif result["moved_to_dlq"]:
                    moved_to_dlq += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(
                    f"Error processing retry {retry.id}: {e}"
                )
                failed += 1

        logger.info(
            f"Retry processing complete: {successful} successful, "
            f"{failed} failed, {moved_to_dlq} moved to DLQ "
            f"out of {processed} total"
        )

        return {
            "processed": processed,
            "successful": successful,
            "failed": failed,
            "moved_to_dlq": moved_to_dlq,
        }

    async def _process_retry(
        self, retry: PaymentRetry, blockchain_service
    ) -> dict:
        """
        Process single retry attempt.

        Args:
            retry: PaymentRetry record
            blockchain_service: Blockchain service

        Returns:
            Dict with success and moved_to_dlq flags
        """
        logger.info(
            f"Processing retry {retry.id} for user {retry.user_id}, "
            f"attempt {retry.attempt_count + 1}/{retry.max_retries}"
        )

        # Increment attempt count
        await self.retry_repo.update(
            retry.id,
            attempt_count=retry.attempt_count + 1,
            last_attempt_at=datetime.utcnow(),
        )

        try:
            # Load user
            user_stmt = select(retry.user)
            user_result = await self.session.execute(user_stmt)
            user = user_result.scalar_one()

            # Validate wallet address
            if not user.wallet_address:
                raise ValueError(
                    f"User {user.telegram_id} has no wallet address"
                )

            # Send payment via blockchain
            logger.info(
                f"Attempting payment: {retry.amount} USDT "
                f"to {user.wallet_address}"
            )

            payment_result = await blockchain_service.send_payment(
                user.wallet_address, float(retry.amount)
            )

            if not payment_result["success"]:
                raise ValueError(
                    payment_result.get("error", "Unknown payment error")
                )

            # Payment succeeded!
            tx_hash = payment_result["tx_hash"]
            logger.info(
                f"Payment retry {retry.id} succeeded! TxHash: {tx_hash}"
            )

            # Mark retry as resolved
            await self.retry_repo.update(
                retry.id, resolved=True, tx_hash=tx_hash
            )

            # Mark earnings/rewards as paid
            if retry.payment_type == PaymentType.REFERRAL_EARNING.value:
                for earning_id in retry.earning_ids:
                    await self.earning_repo.update(
                        earning_id, paid=True, tx_hash=tx_hash
                    )
            elif retry.payment_type == PaymentType.DEPOSIT_REWARD.value:
                for reward_id in retry.earning_ids:
                    await self.reward_repo.update(
                        reward_id,
                        paid=True,
                        paid_at=datetime.utcnow(),
                        tx_hash=tx_hash,
                    )

            # Create transaction record
            tx_type = (
                TransactionType.REFERRAL_REWARD
                if retry.payment_type == PaymentType.REFERRAL_EARNING.value
                else TransactionType.DEPOSIT_REWARD
            )

            await self.transaction_repo.create(
                user_id=retry.user_id,
                tx_hash=tx_hash,
                type=tx_type.value,
                amount=retry.amount,
                from_address="",
                to_address=user.wallet_address,
                status=TransactionStatus.CONFIRMED.value,
            )

            await self.session.commit()

            logger.info(
                "Payment retry succeeded",
                extra={
                    "retry_id": retry.id,
                    "attempt_count": retry.attempt_count,
                    "tx_hash": tx_hash,
                },
            )

            return {"success": True, "moved_to_dlq": False}

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Retry {retry.id} attempt "
                f"{retry.attempt_count} failed: {error_msg}"
            )

            # Update retry with error
            await self.retry_repo.update(
                retry.id, last_error=error_msg
            )

            # Check if max retries exceeded
            if retry.attempt_count >= retry.max_retries:
                # Move to DLQ
                await self.retry_repo.update(
                    retry.id, in_dlq=True, next_retry_at=None
                )

                logger.warning(
                    f"Retry {retry.id} moved to DLQ "
                    f"after {retry.attempt_count} attempts"
                )

                await self.session.commit()

                return {"success": False, "moved_to_dlq": True}
            else:
                # Schedule next retry with exponential backoff
                next_retry = self._calculate_next_retry_time(
                    retry.attempt_count
                )
                await self.retry_repo.update(
                    retry.id, next_retry_at=next_retry
                )

                logger.info(
                    f"Retry {retry.id} scheduled for next attempt "
                    f"at: {next_retry.isoformat()}"
                )

                await self.session.commit()

                return {"success": False, "moved_to_dlq": False}

    def _calculate_next_retry_time(
        self, attempt_count: int
    ) -> datetime:
        """
        Calculate next retry time using exponential backoff.

        Formula: delay = BASE_DELAY * 2^attempt_count
        Example: 1min, 2min, 4min, 8min, 16min

        Args:
            attempt_count: Current attempt count

        Returns:
            Next retry datetime
        """
        delay_minutes = BASE_RETRY_DELAY_MINUTES * (2 ** attempt_count)
        return datetime.utcnow() + timedelta(minutes=delay_minutes)

    async def get_dlq_items(self) -> list[PaymentRetry]:
        """
        Get all DLQ items (for admin review).

        Returns:
            List of DLQ payment retries
        """
        return await self.retry_repo.get_dlq_entries()

    async def retry_dlq_item(
        self, retry_id: int, blockchain_service
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Manually retry DLQ item (admin action).

        Args:
            retry_id: Retry ID
            blockchain_service: Blockchain service

        Returns:
            Tuple of (success, tx_hash, error_message)
        """
        retry = await self.retry_repo.get_by_id(retry_id)

        if not retry:
            return False, None, "Retry record not found"

        if retry.resolved:
            return False, None, "Payment already resolved"

        logger.info(
            f"Manual retry of DLQ item {retry_id} by admin"
        )

        # Remove from DLQ and reset
        await self.retry_repo.update(
            retry_id,
            in_dlq=False,
            attempt_count=0,
            next_retry_at=datetime.utcnow(),
        )

        await self.session.flush()

        # Process the retry
        result = await self._process_retry(retry, blockchain_service)

        if result["success"]:
            return True, retry.tx_hash, None
        else:
            return False, None, retry.last_error or "Retry failed"

    async def get_retry_stats(self) -> dict:
        """
        Get retry statistics.

        Returns:
            Dict with comprehensive retry stats
        """
        # Get counts
        pending = len(
            await self.retry_repo.find_by(
                resolved=False, in_dlq=False
            )
        )
        dlq = len(await self.retry_repo.get_dlq_entries())
        resolved = len(await self.retry_repo.find_by(resolved=True))

        # Get amounts
        all_unresolved = await self.retry_repo.find_by(resolved=False)
        total_amount = sum(r.amount for r in all_unresolved)

        dlq_items = await self.retry_repo.get_dlq_entries()
        dlq_amount = sum(r.amount for r in dlq_items)

        return {
            "pending_retries": pending,
            "dlq_items": dlq,
            "resolved_retries": resolved,
            "total_amount": total_amount,
            "dlq_amount": dlq_amount,
        }

    async def get_user_retries(
        self, user_id: int
    ) -> list[PaymentRetry]:
        """
        Get pending retries for specific user.

        Args:
            user_id: User ID

        Returns:
            List of user's pending retries
        """
        return await self.retry_repo.find_by(
            user_id=user_id, resolved=False
        )
