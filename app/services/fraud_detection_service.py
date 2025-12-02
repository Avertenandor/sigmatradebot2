"""
Fraud Detection Service (R10-1).

Detects suspicious patterns and calculates risk scores for users.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deposit import Deposit
from app.models.enums import TransactionStatus, TransactionType
from app.models.referral import Referral
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.deposit_repository import DepositRepository
from app.repositories.referral_repository import ReferralRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository


class FraudDetectionService:
    """Service for fraud detection and risk scoring."""

    # Risk thresholds
    RISK_THRESHOLD_SUSPICIOUS = 50  # Mark as suspicious
    RISK_THRESHOLD_BLOCK = 80  # Block withdrawals

    def __init__(self, session: AsyncSession) -> None:
        """Initialize fraud detection service."""
        self.session = session
        self.user_repo = UserRepository(session)
        self.deposit_repo = DepositRepository(session)
        self.transaction_repo = TransactionRepository(session)
        self.referral_repo = ReferralRepository(session)

    async def calculate_risk_score(self, user_id: int) -> dict:
        """
        Calculate fraud risk score for user (0-100).

        Args:
            user_id: User ID

        Returns:
            Dict with risk_score, factors, recommendations
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return {
                "risk_score": 0,
                "factors": [],
                "recommendations": [],
            }

        risk_score = 0
        factors = []

        # Factor 1: Multiple registrations from same IP/wallet (simplified)
        # In production, would check IP addresses and wallet addresses
        wallet_users = await self.user_repo.find_by(
            wallet_address=user.wallet_address
        )
        if len(wallet_users) > 1:
            risk_score += 30
            factors.append(
                {
                    "type": "multiple_wallet_registrations",
                    "severity": "high",
                    "description": f"Wallet address used by {len(wallet_users)} users",
                }
            )

        # Factor 2: Suspicious referral patterns
        referral_count = await self._check_referral_patterns(user_id)
        if referral_count > 10:
            risk_score += 20
            factors.append(
                {
                    "type": "excessive_referrals",
                    "severity": "medium",
                    "description": f"User has {referral_count} referrals",
                }
            )

        # Factor 3: Rapid withdrawals after deposit
        rapid_withdrawal = await self._check_rapid_withdrawals(user_id)
        if rapid_withdrawal:
            risk_score += 25
            factors.append(
                {
                    "type": "rapid_withdrawal",
                    "severity": "high",
                    "description": "Withdrawal within 24h of deposit",
                }
            )

        # Factor 4: Multiple failed withdrawal attempts
        failed_attempts = await self._check_failed_withdrawals(user_id)
        if failed_attempts > 3:
            risk_score += 15
            factors.append(
                {
                    "type": "multiple_failed_withdrawals",
                    "severity": "medium",
                    "description": f"{failed_attempts} failed withdrawal attempts",
                }
            )

        # Factor 5: Unusual deposit patterns
        unusual_deposit = await self._check_unusual_deposits(user_id)
        if unusual_deposit:
            risk_score += 10
            factors.append(
                {
                    "type": "unusual_deposit_pattern",
                    "severity": "low",
                    "description": "Unusual deposit timing or amounts",
                }
            )

        # R16-4: Factor 6: Account selling detection
        account_selling = await self._check_account_selling(user_id)
        if account_selling["detected"]:
            risk_score += account_selling["risk_points"]
            factors.append(
                {
                    "type": "account_selling",
                    "severity": account_selling["severity"],
                    "description": account_selling["description"],
                }
            )

        # Cap at 100
        risk_score = min(risk_score, 100)

        # Generate recommendations
        recommendations = []
        if risk_score >= self.RISK_THRESHOLD_BLOCK:
            recommendations.append("block_withdrawals")
            recommendations.append("manual_review")
        elif risk_score >= self.RISK_THRESHOLD_SUSPICIOUS:
            recommendations.append("mark_suspicious")
            recommendations.append("monitor_closely")

        return {
            "risk_score": risk_score,
            "factors": factors,
            "recommendations": recommendations,
        }

    async def check_and_block_if_needed(self, user_id: int) -> dict:
        """
        Check user risk and block if threshold exceeded.

        Args:
            user_id: User ID

        Returns:
            Dict with blocked, risk_score, reason
        """
        risk_result = await self.calculate_risk_score(user_id)
        risk_score = risk_result["risk_score"]

        if risk_score >= self.RISK_THRESHOLD_BLOCK:
            # Block withdrawals
            user = await self.user_repo.get_by_id(user_id)
            if user:
                await self.user_repo.update(
                    user_id,
                    suspicious=True,
                    withdrawal_blocked=True,
                )
                await self.session.commit()

                logger.warning(
                    f"User {user_id} blocked due to high risk score: {risk_score}",
                    extra={
                        "user_id": user_id,
                        "risk_score": risk_score,
                        "factors": risk_result["factors"],
                    },
                )

                # Send fraud alert to admins
                await self._send_fraud_alert(user, risk_score, risk_result["factors"])

                return {
                    "blocked": True,
                    "risk_score": risk_score,
                    "reason": "High risk score detected",
                    "factors": risk_result["factors"],
                }

        elif risk_score >= self.RISK_THRESHOLD_SUSPICIOUS:
            # Mark as suspicious
            user = await self.user_repo.get_by_id(user_id)
            if user:
                await self.user_repo.update(user_id, suspicious=True)
                await self.session.commit()

                logger.info(
                    f"User {user_id} marked as suspicious: {risk_score}",
                    extra={
                        "user_id": user_id,
                        "risk_score": risk_score,
                        "factors": risk_result["factors"],
                    },
                )

        return {
            "blocked": False,
            "risk_score": risk_score,
            "factors": risk_result["factors"],
        }

    async def _check_referral_patterns(self, user_id: int) -> int:
        """Check for suspicious referral patterns."""
        referrals = await self.referral_repo.get_by_referrer(
            referrer_id=user_id, level=1
        )
        return len(referrals)

    async def _check_rapid_withdrawals(self, user_id: int) -> bool:
        """Check for rapid withdrawals after deposit."""
        # Get user's deposits
        deposits = await self.deposit_repo.find_by(
            user_id=user_id,
            status=TransactionStatus.CONFIRMED.value,
        )

        if not deposits:
            return False

        # Check for withdrawals within 24h of deposit
        for deposit in deposits:
            deposit_time = deposit.confirmed_at or deposit.created_at
            if not deposit_time:
                continue

            cutoff_time = deposit_time + timedelta(hours=24)
            # Convert to naive datetime for comparison with Transaction.created_at (naive)
            cutoff_time_naive = cutoff_time.replace(tzinfo=None) if cutoff_time.tzinfo else cutoff_time

            withdrawals = await self.transaction_repo.get_by_user(
                user_id=user_id,
                type=TransactionType.WITHDRAWAL.value,
            )

            for withdrawal in withdrawals:
                if withdrawal.created_at <= cutoff_time_naive:
                    return True

        return False

    async def _check_failed_withdrawals(self, user_id: int) -> int:
        """Count failed withdrawal attempts."""
        withdrawals = await self.transaction_repo.get_by_user(
            user_id=user_id,
            type=TransactionType.WITHDRAWAL.value,
            status=TransactionStatus.FAILED.value,
        )
        return len(withdrawals) if withdrawals else 0

    async def _check_unusual_deposits(self, user_id: int) -> bool:
        """Check for unusual deposit patterns."""
        deposits = await self.deposit_repo.find_by(
            user_id=user_id,
            status=TransactionStatus.CONFIRMED.value,
        )

        if not deposits:
            return False

        # Check for multiple deposits in short time
        if len(deposits) > 5:
            # Check if all within 1 hour
            if len(deposits) > 1:
                first = deposits[0].created_at
                last = deposits[-1].created_at
                if (last - first).total_seconds() < 3600:
                    return True

        return False

    async def _check_account_selling(self, user_id: int) -> dict:
        """
        R16-4: Check for account selling patterns.

        Detects:
        - Frequent telegram_id changes (account recovery used for selling)
        - Rapid wallet address changes
        - Wallet address used by multiple telegram_ids

        Args:
            user_id: User ID

        Returns:
            Dict with detected, risk_points, severity, description
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return {
                "detected": False,
                "risk_points": 0,
                "severity": "low",
                "description": "",
            }

        risk_points = 0
        detected = False
        descriptions = []

        # Check 1: Wallet address used by multiple telegram_ids
        # This indicates account selling (wallet transferred to new owner)
        wallet_users = await self.user_repo.find_by(
            wallet_address=user.wallet_address
        )
        if len(wallet_users) > 1:
            # Check if there are multiple telegram_ids for this wallet
            telegram_ids = {u.telegram_id for u in wallet_users if u.id != user_id}
            if telegram_ids:
                risk_points += 35
                detected = True
                descriptions.append(
                    f"Wallet address used by {len(telegram_ids)} different "
                    f"Telegram accounts (possible account sale)"
                )

        # Check 2: Rapid wallet address change
        # If user has deposits/transactions with different wallet addresses
        # within short time, it might indicate account selling
        deposits = await self.deposit_repo.find_by(user_id=user_id)
        if deposits:
            # Check if deposits have different wallet addresses (if tracked)
            # For now, check if user has transactions with different patterns
            transactions = await self.transaction_repo.get_by_user(user_id=user_id)
            if transactions:
                # Check for rapid activity changes that might indicate account sale
                # (e.g., old account had deposits, new account immediately withdraws)
                confirmed_deposits = [
                    d for d in deposits
                    if d.status == TransactionStatus.CONFIRMED.value
                ]
                withdrawals = [
                    t for t in transactions
                    if t.type == TransactionType.WITHDRAWAL.value
                    and t.status == TransactionStatus.CONFIRMED.value
                ]

                if confirmed_deposits and withdrawals:
                    # Check if withdrawals happened very quickly after deposits
                    # (indicates account sale - new owner withdrawing immediately)
                    for deposit in confirmed_deposits:
                        deposit_time = deposit.confirmed_at or deposit.created_at
                        if not deposit_time:
                            continue
                        # Convert to naive for comparison with Transaction.created_at
                        deposit_time_naive = deposit_time.replace(tzinfo=None) if deposit_time.tzinfo else deposit_time

                        for withdrawal in withdrawals:
                            withdrawal_time = withdrawal.created_at
                            time_diff = (withdrawal_time - deposit_time_naive).total_seconds()

                            # If withdrawal within 1 hour of deposit, suspicious
                            if 0 < time_diff < 3600:
                                risk_points += 25
                                detected = True
                                descriptions.append(
                                    "Rapid withdrawal after deposit "
                                    "(possible account sale - new owner withdrawing)"
                                )
                                break

        # Check 3: Account recovery used recently (might indicate telegram_id change for sale)
        # Note: This would require tracking account recovery history
        # For now, we check if user has been recovered recently
        # (AccountRecoveryService would have updated telegram_id)
        # We can't easily check this without recovery history table,
        # but we can infer from wallet_users check above

        severity = "high" if risk_points >= 35 else "medium" if risk_points >= 25 else "low"

        return {
            "detected": detected,
            "risk_points": risk_points,
            "severity": severity,
            "description": "; ".join(descriptions) if descriptions else "",
        }

    async def _send_fraud_alert(
        self,
        user: User,
        risk_score: int,
        factors: list[dict],
    ) -> None:
        """
        Send fraud alert to all admins.

        Args:
            user: User object
            risk_score: Calculated risk score
            factors: List of risk factors
        """
        try:
            from app.services.notification_service import NotificationService
            from app.repositories.admin_repository import AdminRepository

            admin_repo = AdminRepository(self.session)
            admins = await admin_repo.find_all()

            if not admins:
                logger.warning("No admins found to send fraud alert")
                return

            # Format factors
            factors_text = "\n".join(
                f"• {f['type']}: {f['description']}" for f in factors[:5]
            )

            message = (
                f"🚨 *FRAUD ALERT*\n\n"
                f"👤 User #{user.id}\n"
                f"📱 @{user.username or 'N/A'}\n"
                f"💳 `{user.wallet_address[:10]}...`\n\n"
                f"⚠️ Risk Score: *{risk_score}/100*\n\n"
                f"*Причины:*\n{factors_text}\n\n"
                f"Используйте `/dashboard` для обзора."
            )

            from bot.main import bot_instance

            for admin in admins:
                if admin.telegram_id:
                    try:
                        await bot_instance.send_message(
                            chat_id=admin.telegram_id,
                            text=message,
                            parse_mode="Markdown",
                        )
                        logger.info(
                            f"Fraud alert sent to admin {admin.id}",
                            extra={"user_id": user.id, "risk_score": risk_score},
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to send fraud alert to admin {admin.id}: {e}"
                        )

        except Exception as e:
            logger.error(f"Failed to send fraud alerts: {e}")

