"""
PaymentRetry repository (КРИТИЧНО - PART5).

Data access layer for PaymentRetry model.
"""

from typing import List, Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_retry import PaymentRetry, PaymentType
from app.repositories.base import BaseRepository


class PaymentRetryRepository(BaseRepository[PaymentRetry]):
    """
    PaymentRetry repository (КРИТИЧНО из PART5).

    Handles failed payment retry logic.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize payment retry repository."""
        super().__init__(PaymentRetry, session)

    async def get_pending_retries(
        self,
    ) -> List[PaymentRetry]:
        """
        Get pending retries ready for processing.

        Returns:
            List of pending retries
        """
        now = datetime.now()

        stmt = (
            select(PaymentRetry)
            .where(PaymentRetry.resolved == False)
            .where(PaymentRetry.in_dlq == False)
            .where(
                (PaymentRetry.next_retry_at.is_(None))
                | (PaymentRetry.next_retry_at <= now)
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_dlq_entries(
        self,
    ) -> List[PaymentRetry]:
        """
        Get Dead Letter Queue entries.

        Returns:
            List of DLQ entries
        """
        return await self.find_by(in_dlq=True, resolved=False)

    async def get_by_user(
        self, user_id: int
    ) -> List[PaymentRetry]:
        """
        Get payment retries by user.

        Args:
            user_id: User ID

        Returns:
            List of payment retries
        """
        return await self.find_by(user_id=user_id)

    async def get_unresolved_by_type(
        self, payment_type: PaymentType
    ) -> List[PaymentRetry]:
        """
        Get unresolved retries by payment type.

        Args:
            payment_type: Payment type

        Returns:
            List of unresolved retries
        """
        stmt = (
            select(PaymentRetry)
            .where(PaymentRetry.payment_type == payment_type)
            .where(PaymentRetry.resolved == False)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
