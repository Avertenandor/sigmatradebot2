"""
Withdrawal service.

Handles withdrawal requests, balance validation, and admin processing.
"""

import asyncio
import random
from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.admin_action_escrow import AdminActionEscrow
from app.models.enums import TransactionStatus, TransactionType
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.admin_action_escrow_repository import (
    AdminActionEscrowRepository,
)
from app.repositories.transaction_repository import TransactionRepository

# Minimum withdrawal amount in USDT
MIN_WITHDRAWAL_AMOUNT = Decimal("5.0")

# R9-2: Maximum retries for race condition conflicts
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0  # Base delay in seconds


class WithdrawalService:
    """Withdrawal service for managing withdrawal requests."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize withdrawal service."""
        self.session = session
        self.transaction_repo = TransactionRepository(session)

    async def request_withdrawal(
        self,
        user_id: int,
        amount: Decimal,
        available_balance: Decimal,
    ) -> tuple[Transaction | None, str | None]:
        """
        Request withdrawal with balance deduction.

        R9-2: Uses pessimistic locking with NOWAIT and retry logic
        to prevent race conditions with ROI distribution.

        Args:
            user_id: User ID
            amount: Withdrawal amount
            available_balance: User's available balance (from UserService)

        Returns:
            Tuple of (transaction, error_message)
        """
        # R17-3: Check emergency stop
        if settings.emergency_stop_withdrawals:
            logger.warning(
                f"Withdrawal blocked by emergency stop for user {user_id}"
            )
            return None, (
                "⚠️ Временная приостановка выводов из-за технических работ.\n\n"
                "Ваши средства в безопасности, выводы будут доступны после "
                "восстановления.\n\n"
                "Следите за обновлениями в нашем канале."
            )

        # Validate amount
        if amount < MIN_WITHDRAWAL_AMOUNT:
            return None, (
                f"Минимальная сумма вывода: "
                f"{MIN_WITHDRAWAL_AMOUNT} USDT"
            )

        # R9-2: Retry logic for race condition conflicts
        for attempt in range(MAX_RETRIES):
            try:
                # R9-2: Get user with pessimistic lock (NOWAIT to fail fast on conflict)
                # This prevents waiting if ROI distribution is holding the lock
                # NOWAIT ensures immediate failure instead of blocking
                stmt = (
                    select(User)
                    .where(User.id == user_id)
                    .with_for_update(nowait=True)
                )
                result = await self.session.execute(stmt)
                user = result.scalar_one_or_none()

                if not user:
                    return None, "Пользователь не найден"

                # R15-1: Check if user is banned
                if user.is_banned:
                    return None, (
                        "Ваш аккаунт заблокирован. "
                        "Обратитесь в поддержку для выяснения причин."
                    )

                # R10-1: Check if withdrawals are blocked
                if user.withdrawal_blocked:
                    return None, (
                        "Вывод средств заблокирован. "
                        "Обратитесь в поддержку для выяснения причин."
                    )

                # R15-3: Check if finpass recovery is active
                from app.services.finpass_recovery_service import (
                    FinpassRecoveryService,
                )

                finpass_service = FinpassRecoveryService(self.session)
                if await finpass_service.has_active_recovery(user_id):
                    # R15-3: Freeze existing PENDING withdrawals
                    await self._freeze_pending_withdrawals(user_id)

                    return None, (
                        "Вывод средств временно заблокирован "
                        "из-за активного процесса восстановления "
                        "финансового пароля. "
                        "Дождитесь завершения процедуры восстановления."
                    )

                # R10-1: Check fraud risk before withdrawal
                from app.services.fraud_detection_service import (
                    FraudDetectionService,
                )

                fraud_service = FraudDetectionService(self.session)
                fraud_check = await fraud_service.check_and_block_if_needed(
                    user_id
                )

                if fraud_check.get("blocked"):
                    return None, (
                        "Вывод средств временно заблокирован "
                        "из-за подозрительной активности. "
                        "Обратитесь в поддержку."
                    )

                # Check balance
                if available_balance < amount:
                    return None, (
                        f"Недостаточно средств. Доступно: "
                        f"{available_balance:.2f} USDT"
                    )

                # CRITICAL: Deduct balance BEFORE creating transaction
                balance_before = user.balance
                user.balance = user.balance - amount
                balance_after = user.balance

                # Create withdrawal transaction
                transaction = await self.transaction_repo.create(
                    user_id=user_id,
                    type=TransactionType.WITHDRAWAL.value,
                    amount=amount,
                    balance_before=balance_before,
                    balance_after=balance_after,
                    to_address=user.wallet_address,
                    status=TransactionStatus.PENDING.value,
                )

                await self.session.commit()

                logger.info(
                    "Withdrawal request created and balance deducted",
                    extra={
                        "transaction_id": transaction.id,
                        "user_id": user_id,
                        "amount": str(amount),
                        "balance_before": str(balance_before),
                        "balance_after": str(balance_after),
                    },
                )

                return transaction, None

            except OperationalError as e:
                # R9-2: Handle lock conflict (could be race with ROI distribution)
                error_str = str(e).lower()
                if "could not obtain lock" in error_str or "lock_not_available" in error_str:
                    if attempt < MAX_RETRIES - 1:
                        # Retry with exponential backoff + random jitter
                        delay = RETRY_DELAY_BASE * (2 ** attempt) + random.uniform(0, 0.5)
                        logger.info(
                            f"Withdrawal lock conflict for user {user_id}, "
                            f"retrying in {delay:.2f}s (attempt {attempt + 1}/{MAX_RETRIES})"
                        )
                        await self.session.rollback()
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.warning(
                            f"Withdrawal lock conflict for user {user_id} "
                            f"after {MAX_RETRIES} attempts"
                        )
                        await self.session.rollback()
                        return None, (
                            "Система временно занята. "
                            "Попробуйте через несколько секунд."
                        )
                else:
                    # Other database error
                    await self.session.rollback()
                    logger.error(f"Database error in withdrawal: {e}")
                    # R14-3: Record error for aggregation
                    try:
                        from app.services.log_aggregation_service import (
                            LogAggregationService,
                        )
                        agg_service = LogAggregationService(self.session)
                        await agg_service.record_error(
                            error_type="DatabaseError",
                            error_message=str(e)[:500],
                            user_id=user_id,
                            context={"service": "WithdrawalService", "operation": "request_withdrawal"},
                        )
                    except Exception as agg_error:
                        logger.debug(f"Failed to record error in aggregation: {agg_error}")
                    return None, "Ошибка базы данных. Попробуйте позже."

            except Exception as e:
                await self.session.rollback()
                logger.error(f"Failed to create withdrawal: {e}", exc_info=True)
                # R14-3: Record error for aggregation
                try:
                    from app.services.log_aggregation_service import (
                        LogAggregationService,
                    )
                    agg_service = LogAggregationService(self.session)
                    await agg_service.record_error(
                        error_type=type(e).__name__,
                        error_message=str(e)[:500],
                        user_id=user_id,
                        context={"service": "WithdrawalService", "operation": "request_withdrawal"},
                    )
                except Exception as agg_error:
                    logger.debug(f"Failed to record error in aggregation: {agg_error}")
                return None, "Ошибка создания заявки на вывод"

    async def get_pending_withdrawals(
        self,
    ) -> list[Transaction]:
        """
        Get pending withdrawals (for admin).

        Returns:
            List of pending withdrawal transactions
        """
        stmt = (
            select(Transaction)
            .where(
                Transaction.type == TransactionType.WITHDRAWAL.value,
                Transaction.status == TransactionStatus.PENDING.value,
            )
            .order_by(Transaction.created_at.asc())
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_withdrawals(
        self,
        user_id: int,
        page: int = 1,
        limit: int = 10,
    ) -> dict:
        """
        Get user withdrawal history.

        Args:
            user_id: User ID
            page: Page number (1-indexed)
            limit: Items per page

        Returns:
            Dict with withdrawals, total, page, pages
        """
        offset = (page - 1) * limit

        # Get total count
        count_stmt = select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.WITHDRAWAL.value,
        )
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))

        # Get paginated withdrawals
        stmt = (
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.WITHDRAWAL.value,
            )
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        withdrawals = list(result.scalars().all())

        pages = (total + limit - 1) // limit  # Ceiling division

        return {
            "withdrawals": withdrawals,
            "total": total,
            "page": page,
            "pages": pages,
        }

    async def cancel_withdrawal(
        self, transaction_id: int, user_id: int
    ) -> tuple[bool, str | None]:
        """
        Cancel withdrawal and RETURN BALANCE to user.

        Args:
            transaction_id: Transaction ID
            user_id: User ID (for authorization)

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get transaction with lock
            stmt_tx = select(Transaction).where(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.WITHDRAWAL.value,
                Transaction.status == TransactionStatus.PENDING.value,
            ).with_for_update()

            result_tx = await self.session.execute(stmt_tx)
            transaction = result_tx.scalar_one_or_none()

            if not transaction:
                return False, "Заявка не найдена или не может быть отменена"

            # Get user with lock
            stmt_user = (
                select(User).where(User.id == user_id).with_for_update()
            )
            result_user = await self.session.execute(stmt_user)
            user = result_user.scalar_one_or_none()

            if not user:
                return False, "Пользователь не найден"

            # CRITICAL: Return balance to user
            user.balance = user.balance + transaction.amount

            # Update transaction status
            transaction.status = TransactionStatus.FAILED.value

            await self.session.commit()

            logger.info(
                "Withdrawal cancelled and balance returned",
                extra={
                    "transaction_id": transaction_id,
                    "user_id": user_id,
                    "amount": str(transaction.amount),
                    "new_balance": str(user.balance),
                },
            )

            return True, None

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to cancel withdrawal: {e}")
            return False, "Ошибка отмены заявки"

    async def approve_withdrawal(
        self,
        transaction_id: int,
        tx_hash: str,
        admin_id: int | None = None,
    ) -> tuple[bool, str | None]:
        """
        Approve withdrawal (admin only).

        R18-4: This method is called after dual control is completed
        (escrow approved by second admin) or for small withdrawals.

        Args:
            transaction_id: Transaction ID
            tx_hash: Blockchain transaction hash
            admin_id: Admin ID (for logging)

        Returns:
            Tuple of (success, error_message)
        """
        from decimal import Decimal

        try:
            stmt = select(Transaction).where(
                Transaction.id == transaction_id,
                Transaction.type == TransactionType.WITHDRAWAL.value,
                Transaction.status == TransactionStatus.PENDING.value,
            ).with_for_update()

            result = await self.session.execute(stmt)
            withdrawal = result.scalar_one_or_none()

            if not withdrawal:
                return (
                    False,
                    "Заявка на вывод не найдена или уже обработана",
                )

            # R18-4: Dual control is handled in handler.
            # This method is called only after escrow is approved or for small withdrawals.

            # Update withdrawal status to PROCESSING
            withdrawal.status = TransactionStatus.PROCESSING.value
            withdrawal.tx_hash = tx_hash
            await self.session.commit()

            logger.info(
                "Withdrawal approved",
                extra={
                    "transaction_id": transaction_id,
                    "user_id": withdrawal.user_id,
                    "amount": str(withdrawal.amount),
                    "tx_hash": tx_hash,
                    "admin_id": admin_id,
                },
            )

            return True, None

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to approve withdrawal: {e}")
            return False, "Ошибка подтверждения заявки"

    async def approve_withdrawal_via_escrow(
        self,
        escrow_id: int,
        approver_admin_id: int,
        blockchain_service: Any,
    ) -> tuple[bool, str | None, str | None]:
        """
        Approve withdrawal via escrow (second admin).

        R18-4: Second admin approves the escrow, withdrawal is executed.

        Args:
            escrow_id: Escrow ID
            approver_admin_id: Admin who approves
            blockchain_service: Blockchain service for sending payment

        Returns:
            Tuple of (success, error_message, tx_hash)
        """
        try:
            escrow_repo = AdminActionEscrowRepository(self.session)

            # Get escrow
            escrow = await escrow_repo.get_by_id(escrow_id)

            if not escrow:
                return False, "Escrow не найден", None

            if escrow.status != "PENDING":
                return False, f"Escrow уже обработан (статус: {escrow.status})", None

            if escrow.operation_type != "WITHDRAWAL_APPROVAL":
                return False, "Неподдерживаемый тип операции", None

            if escrow.initiator_admin_id == approver_admin_id:
                return False, "Нельзя одобрить собственную инициацию", None

            # Get withdrawal details from escrow
            transaction_id = escrow.operation_data.get("transaction_id")
            withdrawal_amount = float(escrow.operation_data.get("amount", 0))
            to_address = escrow.operation_data.get("to_address")

            if not transaction_id or not to_address:
                return False, "Неверные данные в escrow", None

            # R7-5: Check maintenance mode
            if settings.blockchain_maintenance_mode:
                return False, "Blockchain в режиме обслуживания", None

            # Send blockchain transaction (only after second approval)
            payment_result = await blockchain_service.send_payment(
                to_address, withdrawal_amount
            )

            if not payment_result["success"]:
                error_msg = payment_result.get("error", "Неизвестная ошибка")
                return False, f"Ошибка отправки в блокчейн: {error_msg}", None

            tx_hash = payment_result["tx_hash"]

            # Approve escrow
            approved_escrow = await escrow_repo.approve(escrow_id, approver_admin_id)

            if not approved_escrow:
                return False, "Ошибка при подтверждении escrow", None

            # Approve withdrawal (escrow already approved)
            success, error_msg = await self.approve_withdrawal(
                transaction_id, tx_hash, approver_admin_id
            )

            if not success:
                await self.session.rollback()
                return False, error_msg or "Ошибка при одобрении вывода", None

            await self.session.commit()

            logger.info(
                "R18-4: Withdrawal approved via dual control",
                extra={
                    "escrow_id": escrow_id,
                    "transaction_id": transaction_id,
                    "initiator_admin_id": escrow.initiator_admin_id,
                    "approver_admin_id": approver_admin_id,
                    "amount": withdrawal_amount,
                    "tx_hash": tx_hash,
                },
            )

            return True, None, tx_hash

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to approve withdrawal via escrow: {e}")
            return False, f"Ошибка при одобрении через escrow: {str(e)}", None

    async def reject_withdrawal(
        self, transaction_id: int, reason: str | None = None
    ) -> tuple[bool, str | None]:
        """
        Reject withdrawal and RETURN BALANCE to user (admin only).

        Args:
            transaction_id: Transaction ID
            reason: Rejection reason (for logging)

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get transaction with lock
            stmt_tx = select(Transaction).where(
                Transaction.id == transaction_id,
                Transaction.type == TransactionType.WITHDRAWAL.value,
                Transaction.status == TransactionStatus.PENDING.value,
            ).with_for_update()

            result_tx = await self.session.execute(stmt_tx)
            withdrawal = result_tx.scalar_one_or_none()

            if not withdrawal:
                return (
                    False,
                    "Заявка на вывод не найдена или уже обработана",
                )

            # Get user with lock
            stmt_user = (
                select(User)
                .where(User.id == withdrawal.user_id)
                .with_for_update()
            )
            result_user = await self.session.execute(stmt_user)
            user = result_user.scalar_one_or_none()

            if user:
                # CRITICAL: Return balance to user
                user.balance = user.balance + withdrawal.amount

            # Update withdrawal status
            withdrawal.status = TransactionStatus.FAILED.value
            await self.session.commit()

            logger.info(
                "Withdrawal rejected and balance returned",
                extra={
                    "transaction_id": transaction_id,
                    "user_id": withdrawal.user_id,
                    "amount": str(withdrawal.amount),
                    "new_balance": str(user.balance) if user else "N/A",
                    "reason": reason,
                },
            )

            return True, None

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to reject withdrawal: {e}")
            return False, "Ошибка отклонения заявки"

    async def get_withdrawal_by_id(
        self, transaction_id: int
    ) -> Transaction | None:
        """
        Get withdrawal by ID (admin only).

        Args:
            transaction_id: Transaction ID

        Returns:
            Transaction or None
        """
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.type == TransactionType.WITHDRAWAL.value,
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _freeze_pending_withdrawals(self, user_id: int) -> None:
        """
        Freeze pending withdrawals for user (R15-3).

        When finpass recovery is active, existing PENDING withdrawals
        are frozen (marked as FAILED and balance returned).

        Args:
            user_id: User ID
        """
        # Get pending withdrawals
        pending = await self.transaction_repo.get_by_user(
            user_id=user_id,
            type=TransactionType.WITHDRAWAL.value,
            status=TransactionStatus.PENDING.value,
        )

        if not pending:
            return

        # Get user with lock
        stmt = select(User).where(User.id == user_id).with_for_update()
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return

        # Return balance and mark as failed
        for withdrawal in pending:
            user.balance = user.balance + withdrawal.amount
            withdrawal.status = TransactionStatus.FAILED.value

            logger.info(
                f"Frozen withdrawal {withdrawal.id} due to finpass recovery",
                extra={
                    "withdrawal_id": withdrawal.id,
                    "user_id": user_id,
                    "amount": str(withdrawal.amount),
                },
            )

        await self.session.commit()

    async def handle_successful_withdrawal_with_old_password(
        self, user_id: int
    ) -> None:
        """
        Handle successful withdrawal with old password (R15-3).

        Automatically reject active finpass recovery if user successfully
        withdraws with old password.

        Args:
            user_id: User ID
        """
        from app.services.finpass_recovery_service import (
            FinpassRecoveryService,
        )

        finpass_service = FinpassRecoveryService(self.session)
        active_recovery = await finpass_service.get_pending_by_user(user_id)

        if active_recovery:
            # Reject recovery request
            await finpass_service.reject_recovery(
                recovery_id=active_recovery.id,
                admin_id=None,  # System rejection
                reason="User successfully withdrew with old password",
            )

            logger.info(
                f"Auto-rejected finpass recovery {active_recovery.id} "
                f"for user {user_id} after successful withdrawal",
            )

    @staticmethod
    def get_min_withdrawal_amount() -> Decimal:
        """
        Get minimum withdrawal amount.

        Returns:
            Minimum withdrawal amount in USDT
        """
        return MIN_WITHDRAWAL_AMOUNT
