"""
Withdrawal service.

Handles withdrawal requests, balance validation, auto-withdrawals, and admin processing.
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
from app.models.global_settings import GlobalSettings
from app.repositories.admin_action_escrow_repository import (
    AdminActionEscrowRepository,
)
from app.repositories.deposit_repository import DepositRepository
from app.repositories.global_settings_repository import GlobalSettingsRepository
from app.repositories.transaction_repository import TransactionRepository

# R9-2: Maximum retries for race condition conflicts
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0  # Base delay in seconds


class WithdrawalService:
    """Withdrawal service for managing withdrawal requests."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize withdrawal service."""
        self.session = session
        self.transaction_repo = TransactionRepository(session)
        self.settings_repo = GlobalSettingsRepository(session)

    async def get_min_withdrawal_amount(self) -> Decimal:
        """
        Get minimum withdrawal amount from global settings.
        """
        settings = await self.settings_repo.get_settings()
        return settings.min_withdrawal_amount

    async def _check_auto_withdrawal_eligibility(
        self,
        user_id: int,
        amount: Decimal,
        settings: GlobalSettings
    ) -> bool:
        """
        Check if withdrawal is eligible for auto-approval.
        
        Logic:
        1. Auto-withdrawal must be enabled globally.
        2. x5 Rule: (Total Withdrawn + Request) <= (Total Deposited * 5)
        3. Global Daily Limit: Today's Total + Request <= Limit (if enabled)
        """
        if not settings.auto_withdrawal_enabled:
            return False

        # 1. Check x5 Rule (Math Validation)
        deposit_repo = DepositRepository(self.session)
        total_deposited = await deposit_repo.get_total_deposited(user_id)
        
        # If no deposits, no auto withdrawal
        if total_deposited <= 0:
            return False
            
        max_payout = total_deposited * Decimal("5.0")
        
        total_withdrawn = await self.transaction_repo.get_total_withdrawn(user_id)
        
        if (total_withdrawn + amount) > max_payout:
            logger.info(
                f"Auto-withdrawal denied for user {user_id}: Limit x5 exceeded. "
                f"Deposited: {total_deposited}, Max Payout: {max_payout}, "
                f"Withdrawn: {total_withdrawn}, Request: {amount}"
            )
            return False
            
        # 2. Check Global Daily Limit (Circuit Breaker)
        if settings.is_daily_limit_enabled and settings.daily_withdrawal_limit:
            today_total = await self.transaction_repo.get_total_withdrawn_today()
            if (today_total + amount) > settings.daily_withdrawal_limit:
                logger.warning(
                    f"Auto-withdrawal denied: Global daily limit exceeded. "
                    f"Today: {today_total}, Request: {amount}, "
                    f"Limit: {settings.daily_withdrawal_limit}"
                )
                return False
                
        return True

    async def request_withdrawal(
        self,
        user_id: int,
        amount: Decimal,
        available_balance: Decimal,
    ) -> tuple[Transaction | None, str | None, bool]:
        """
        Request withdrawal with balance deduction.

        Args:
            user_id: User ID
            amount: Withdrawal amount
            available_balance: User's available balance

        Returns:
            Tuple of (transaction, error_message, is_auto_approved)
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
            ), False

        # Load global settings
        global_settings = await self.settings_repo.get_settings()
        min_amount = global_settings.min_withdrawal_amount

        # Validate amount
        if amount < min_amount:
            return None, (
                f"Минимальная сумма вывода: "
                f"{min_amount} USDT"
            ), False

        # R9-2: Retry logic for race condition conflicts
        for attempt in range(MAX_RETRIES):
            try:
                # Get user with pessimistic lock (NOWAIT)
                stmt = (
                    select(User)
                    .where(User.id == user_id)
                    .with_for_update(nowait=True)
                )
                result = await self.session.execute(stmt)
                user = result.scalar_one_or_none()

                if not user:
                    return None, "Пользователь не найден", False

                # R15-1: Check if user is banned
                if user.is_banned:
                    return None, (
                        "Ваш аккаунт заблокирован. "
                        "Обратитесь в поддержку для выяснения причин."
                    ), False

                # R10-1: Check if withdrawals are blocked
                if user.withdrawal_blocked:
                    return None, (
                        "Вывод средств заблокирован. "
                        "Обратитесь в поддержку для выяснения причин."
                    ), False

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
                    ), False

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
                    ), False

                # Check balance
                if available_balance < amount:
                    return None, (
                        f"Недостаточно средств. Доступно: "
                        f"{available_balance:.2f} USDT"
                    ), False

                # Deduct balance BEFORE creating transaction
                balance_before = user.balance
                user.balance = user.balance - amount
                balance_after = user.balance

                # Check Auto-Withdrawal Eligibility
                is_auto = await self._check_auto_withdrawal_eligibility(
                    user_id, amount, global_settings
                )
                
                status = TransactionStatus.PROCESSING.value if is_auto else TransactionStatus.PENDING.value

                # Create withdrawal transaction
                transaction = await self.transaction_repo.create(
                    user_id=user_id,
                    type=TransactionType.WITHDRAWAL.value,
                    amount=amount,
                    balance_before=balance_before,
                    balance_after=balance_after,
                    to_address=user.wallet_address,
                    status=status,
                )

                await self.session.commit()

                logger.info(
                    "Withdrawal request created",
                    extra={
                        "transaction_id": transaction.id,
                        "user_id": user_id,
                        "amount": str(amount),
                        "status": status,
                        "is_auto": is_auto,
                    },
                )

                return transaction, None, is_auto

            except OperationalError as e:
                # Handle lock conflict
                error_str = str(e).lower()
                if "could not obtain lock" in error_str or "lock_not_available" in error_str:
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAY_BASE * (2 ** attempt) + random.uniform(0, 0.5)
                        await self.session.rollback()
                        await asyncio.sleep(delay)
                        continue
                    else:
                        await self.session.rollback()
                        return None, (
                            "Система временно занята. "
                            "Попробуйте через несколько секунд."
                        ), False
                else:
                    await self.session.rollback()
                    logger.error(f"Database error in withdrawal: {e}")
                    return None, "Ошибка базы данных. Попробуйте позже.", False

            except Exception as e:
                await self.session.rollback()
                logger.error(f"Failed to create withdrawal: {e}", exc_info=True)
                return None, "Ошибка создания заявки на вывод", False

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
        try:
            stmt = select(Transaction).where(
                Transaction.id == transaction_id,
                Transaction.type == TransactionType.WITHDRAWAL.value,
                # Can approve PENDING or PROCESSING (if auto-withdrawal failed or stuck)
                Transaction.status.in_([TransactionStatus.PENDING.value, TransactionStatus.PROCESSING.value]),
            ).with_for_update()

            result = await self.session.execute(stmt)
            withdrawal = result.scalar_one_or_none()

            if not withdrawal:
                return (
                    False,
                    "Заявка на вывод не найдена или уже обработана",
                )

            # Update withdrawal status to PROCESSING (or COMPLETED? Logic says approve means we HAVE tx_hash)
            # If we pass tx_hash, it means it is DONE (or submitted).
            # Usually approve_withdrawal marks it as PROCESSING, and blockchain callback marks as COMPLETED.
            # But here we pass tx_hash, so it means it was sent.
            
            # Let's keep it PROCESSING for now, background job will check receipt.
            withdrawal.status = TransactionStatus.PROCESSING.value
            withdrawal.tx_hash = tx_hash
            await self.session.commit()

            logger.info(
                "Withdrawal approved/updated with tx_hash",
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
        """
        try:
            escrow_repo = AdminActionEscrowRepository(self.session)
            escrow = await escrow_repo.get_by_id(escrow_id)

            if not escrow:
                return False, "Escrow не найден", None

            if escrow.status != "PENDING":
                return False, f"Escrow уже обработан (статус: {escrow.status})", None

            if escrow.operation_type != "WITHDRAWAL_APPROVAL":
                return False, "Неподдерживаемый тип операции", None

            if escrow.initiator_admin_id == approver_admin_id:
                return False, "Нельзя одобрить собственную инициацию", None

            transaction_id = escrow.operation_data.get("transaction_id")
            withdrawal_amount = float(escrow.operation_data.get("amount", 0))
            to_address = escrow.operation_data.get("to_address")

            if not transaction_id or not to_address:
                return False, "Неверные данные в escrow", None

            if settings.blockchain_maintenance_mode:
                return False, "Blockchain в режиме обслуживания", None

            payment_result = await blockchain_service.send_payment(
                to_address, withdrawal_amount
            )

            if not payment_result["success"]:
                error_msg = payment_result.get("error", "Неизвестная ошибка")
                return False, f"Ошибка отправки в блокчейн: {error_msg}", None

            tx_hash = payment_result["tx_hash"]

            approved_escrow = await escrow_repo.approve(escrow_id, approver_admin_id)

            if not approved_escrow:
                return False, "Ошибка при подтверждении escrow", None

            success, error_msg = await self.approve_withdrawal(
                transaction_id, tx_hash, approver_admin_id
            )

            if not success:
                await self.session.rollback()
                return False, error_msg or "Ошибка при одобрении вывода", None

            await self.session.commit()

            return True, None, tx_hash

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to approve withdrawal via escrow: {e}")
            return False, f"Ошибка при одобрении через escrow: {str(e)}", None

    async def reject_withdrawal(
        self, transaction_id: int, reason: str | None = None
    ) -> tuple[bool, str | None]:
        """Reject withdrawal and RETURN BALANCE."""
        try:
            stmt_tx = select(Transaction).where(
                Transaction.id == transaction_id,
                Transaction.type == TransactionType.WITHDRAWAL.value,
                Transaction.status == TransactionStatus.PENDING.value,
            ).with_for_update()

            result_tx = await self.session.execute(stmt_tx)
            withdrawal = result_tx.scalar_one_or_none()

            if not withdrawal:
                return (False, "Заявка на вывод не найдена или уже обработана")

            stmt_user = (
                select(User)
                .where(User.id == withdrawal.user_id)
                .with_for_update()
            )
            result_user = await self.session.execute(stmt_user)
            user = result_user.scalar_one_or_none()

            if user:
                user.balance = user.balance + withdrawal.amount

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
        """Get withdrawal by ID (admin only)."""
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.type == TransactionType.WITHDRAWAL.value,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _freeze_pending_withdrawals(self, user_id: int) -> None:
        """Freeze pending withdrawals for user."""
        pending = await self.transaction_repo.get_by_user(
            user_id=user_id,
            type=TransactionType.WITHDRAWAL.value,
            status=TransactionStatus.PENDING.value,
        )

        if not pending:
            return

        stmt = select(User).where(User.id == user_id).with_for_update()
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return

        for withdrawal in pending:
            user.balance = user.balance + withdrawal.amount
            withdrawal.status = TransactionStatus.FAILED.value

        await self.session.commit()

    async def handle_successful_withdrawal_with_old_password(
        self, user_id: int
    ) -> None:
        """Handle successful withdrawal with old password."""
        from app.services.finpass_recovery_service import (
            FinpassRecoveryService,
        )

        finpass_service = FinpassRecoveryService(self.session)
        active_recovery = await finpass_service.get_pending_by_user(user_id)

        if active_recovery:
            await finpass_service.reject_recovery(
                recovery_id=active_recovery.id,
                admin_id=None,
                reason="User successfully withdrew with old password",
            )
