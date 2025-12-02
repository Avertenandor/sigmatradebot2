"""
Metrics Monitor Service (R14-1).

Monitors financial metrics and detects anomalies using statistical methods.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deposit import Deposit
from app.models.enums import TransactionStatus, TransactionType
from app.models.transaction import Transaction
from app.repositories.deposit_repository import DepositRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository


class MetricsMonitorService:
    """Service for monitoring financial metrics and detecting anomalies."""

    # Z-score threshold for anomaly detection
    Z_SCORE_THRESHOLD = 3.0

    # Critical severity threshold (triggers automatic actions)
    CRITICAL_SEVERITY_THRESHOLD = 5.0

    def __init__(self, session: AsyncSession) -> None:
        """Initialize metrics monitor service."""
        self.session = session
        self.user_repo = UserRepository(session)
        self.deposit_repo = DepositRepository(session)
        self.transaction_repo = TransactionRepository(session)

    async def collect_current_metrics(self) -> dict[str, Any]:
        """
        Collect current financial metrics (R14-1).

        Returns:
            Dict with current metrics
        """
        now = datetime.now(UTC)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        # Withdrawal metrics
        pending_withdrawals = await self.transaction_repo.find_by(
            type=TransactionType.WITHDRAWAL.value,
            status=TransactionStatus.PENDING.value,
        )
        pending_count = len(pending_withdrawals) if pending_withdrawals else 0

        # Withdrawals in last hour
        withdrawals_last_hour = await self._get_withdrawals_in_period(
            hour_ago, now
        )
        withdrawal_amount_last_hour = float(sum(
            w.amount for w in withdrawals_last_hour
        ))

        # Rejected withdrawals (in last hour)
        rejected_count = len([
            w for w in withdrawals_last_hour
            if w.status == TransactionStatus.FAILED.value
        ])
        
        total_withdrawals = (
            len(withdrawals_last_hour) if withdrawals_last_hour else 0
        )
        rejection_rate = (
            (rejected_count / total_withdrawals * 100)
            if total_withdrawals > 0
            else 0
        )

        # Deposit metrics
        deposits_last_day = await self._get_deposits_in_period(day_ago, now)
        deposit_count = len(deposits_last_day) if deposits_last_day else 0

        # Level 5 deposits (max level)
        level_5_deposits = [
            d for d in deposits_last_day if d.level == 5
        ]
        level_5_count = len(level_5_deposits)

        # Balance metrics
        total_balance = await self._get_total_user_balance()
        total_deposits = await self._get_total_confirmed_deposits()
        total_withdrawals_all = await self._get_total_confirmed_withdrawals()

        # Referral metrics
        referral_earnings = await self._get_referral_earnings_last_day(day_ago)

        return {
            "timestamp": now.isoformat(),
            "withdrawals": {
                "pending_count": pending_count,
                "last_hour_count": len(withdrawals_last_hour)
                if withdrawals_last_hour
                else 0,
                "last_hour_amount": withdrawal_amount_last_hour,
                "rejected_count": rejected_count,
                "rejection_rate": rejection_rate,
            },
            "deposits": {
                "last_day_count": deposit_count,
                "level_5_count": level_5_count,
            },
            "balance": {
                "total_user_balance": float(total_balance),
                "total_deposits": float(total_deposits),
                "total_withdrawals": float(total_withdrawals_all),
                "system_liabilities": float(total_balance),
            },
            "referrals": {
                "earnings_last_day": float(referral_earnings),
            },
        }

    async def detect_anomalies(
        self, current_metrics: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Detect anomalies using z-score method (R14-1).

        Args:
            current_metrics: Current metrics dict

        Returns:
            List of detected anomalies
        """
        anomalies = []

        # Get historical baseline (last 7 days)
        baseline = await self._get_historical_baseline(days=7)

        # Check withdrawal metrics
        if "withdrawals" in current_metrics:
            w_metrics = current_metrics["withdrawals"]

            # Pending withdrawals spike
            if "pending_count" in w_metrics:
                z_score = self._calculate_z_score(
                    w_metrics["pending_count"],
                    baseline.get("pending_withdrawals_mean", 0),
                    baseline.get("pending_withdrawals_std", 1),
                )
                if abs(z_score) > self.Z_SCORE_THRESHOLD:
                    anomalies.append(
                        {
                            "type": "withdrawal_pending_spike",
                            "metric": "pending_withdrawals",
                            "current": w_metrics["pending_count"],
                            "expected_mean": baseline.get(
                                "pending_withdrawals_mean", 0
                            ),
                            "z_score": z_score,
                            "severity": "critical"
                            if abs(z_score) > self.CRITICAL_SEVERITY_THRESHOLD
                            else "high",
                        }
                    )

            # Withdrawal amount spike
            if "last_hour_amount" in w_metrics:
                z_score = self._calculate_z_score(
                    w_metrics["last_hour_amount"],
                    baseline.get("withdrawal_amount_mean", 0),
                    baseline.get("withdrawal_amount_std", 1),
                )
                if abs(z_score) > self.Z_SCORE_THRESHOLD:
                    anomalies.append(
                        {
                            "type": "withdrawal_amount_spike",
                            "metric": "withdrawal_amount",
                            "current": w_metrics["last_hour_amount"],
                            "expected_mean": baseline.get(
                                "withdrawal_amount_mean", 0
                            ),
                            "z_score": z_score,
                            "severity": "critical"
                            if abs(z_score) > self.CRITICAL_SEVERITY_THRESHOLD
                            else "high",
                        }
                    )

            # Rejection rate spike
            if "rejection_rate" in w_metrics:
                z_score = self._calculate_z_score(
                    w_metrics["rejection_rate"],
                    baseline.get("rejection_rate_mean", 2.0),
                    baseline.get("rejection_rate_std", 1.0),
                )
                if abs(z_score) > self.Z_SCORE_THRESHOLD:
                    anomalies.append(
                        {
                            "type": "rejection_rate_spike",
                            "metric": "rejection_rate",
                            "current": w_metrics["rejection_rate"],
                            "expected_mean": baseline.get(
                                "rejection_rate_mean", 2.0
                            ),
                            "z_score": z_score,
                            "severity": "high",
                        }
                    )

        # Check deposit metrics
        if "deposits" in current_metrics:
            d_metrics = current_metrics["deposits"]

            # Low deposit count
            if "last_day_count" in d_metrics:
                z_score = self._calculate_z_score(
                    d_metrics["last_day_count"],
                    baseline.get("deposit_count_mean", 50),
                    baseline.get("deposit_count_std", 10),
                )
                if z_score < -self.Z_SCORE_THRESHOLD:
                    anomalies.append(
                        {
                            "type": "deposit_count_low",
                            "metric": "deposit_count",
                            "current": d_metrics["last_day_count"],
                            "expected_mean": baseline.get(
                                "deposit_count_mean", 50
                            ),
                            "z_score": z_score,
                            "severity": "medium",
                        }
                    )

            # Level 5 spike
            if "level_5_count" in d_metrics:
                z_score = self._calculate_z_score(
                    d_metrics["level_5_count"],
                    baseline.get("level_5_count_mean", 5),
                    baseline.get("level_5_count_std", 2),
                )
                if abs(z_score) > self.Z_SCORE_THRESHOLD:
                    anomalies.append(
                        {
                            "type": "level_5_deposit_spike",
                            "metric": "level_5_deposits",
                            "current": d_metrics["level_5_count"],
                            "expected_mean": baseline.get(
                                "level_5_count_mean", 5
                            ),
                            "z_score": z_score,
                            "severity": "high",
                        }
                    )

        # Check balance metrics
        if "balance" in current_metrics:
            b_metrics = current_metrics["balance"]

            # System liabilities spike
            if "system_liabilities" in b_metrics:
                z_score = self._calculate_z_score(
                    b_metrics["system_liabilities"],
                    baseline.get("system_liabilities_mean", 0),
                    baseline.get("system_liabilities_std", 1000),
                )
                if abs(z_score) > self.Z_SCORE_THRESHOLD:
                    anomalies.append(
                        {
                            "type": "system_liabilities_spike",
                            "metric": "system_liabilities",
                            "current": b_metrics["system_liabilities"],
                            "expected_mean": baseline.get(
                                "system_liabilities_mean", 0
                            ),
                            "z_score": z_score,
                            "severity": "critical"
                            if abs(z_score) > self.CRITICAL_SEVERITY_THRESHOLD
                            else "high",
                        }
                    )

        return anomalies

    def _calculate_z_score(
        self, value: float, mean: float, std_dev: float
    ) -> float:
        """
        Calculate z-score for anomaly detection.

        Args:
            value: Current value
            mean: Historical mean
            std_dev: Standard deviation

        Returns:
            Z-score
        """
        if std_dev == 0:
            return 0.0

        return (value - mean) / std_dev

    async def _get_historical_baseline(
        self, days: int = 30
    ) -> dict[str, float]:
        """
        Calculate historical baseline from actual data.

        Args:
            days: Number of days to look back (default 30)

        Returns:
            Dict with mean and std_dev for each metric
        """
        import statistics
        
        now = datetime.now(UTC)
        
        # Collect daily metrics for the past N days
        daily_deposit_counts: list[int] = []
        daily_withdrawal_amounts: list[float] = []
        daily_level_5_counts: list[int] = []
        
        for i in range(days):
            day_start = (now - timedelta(days=i + 1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)
            
            # Deposits for this day
            deposits = await self._get_deposits_in_period(day_start, day_end)
            daily_deposit_counts.append(len(deposits))
            daily_level_5_counts.append(
                len([d for d in deposits if d.level == 5])
            )
            
            # Withdrawals for this day
            withdrawals = await self._get_withdrawals_in_period(day_start, day_end)
            daily_withdrawal_amounts.append(
                float(sum(w.amount for w in withdrawals))
            )
        
        # Current pending withdrawals (snapshot metric, not daily)
        pending = await self.transaction_repo.find_by(
            type=TransactionType.WITHDRAWAL.value,
            status=TransactionStatus.PENDING.value,
        )
        pending_count = len(pending) if pending else 0
        
        # Current system liabilities
        system_liabilities = float(await self._get_total_user_balance())
        
        # Calculate statistics with fallback for insufficient data
        def safe_mean(data: list, default: float = 0.0) -> float:
            return statistics.mean(data) if len(data) >= 2 else default
        
        def safe_stdev(data: list, default: float = 1.0) -> float:
            if len(data) < 2:
                return default
            try:
                return max(statistics.stdev(data), 0.1)  # Minimum 0.1 to avoid div by 0
            except statistics.StatisticsError:
                return default
        
        # Build baseline from actual data
        deposit_mean = safe_mean(daily_deposit_counts, 0.0)
        deposit_std = safe_stdev(daily_deposit_counts, max(deposit_mean * 0.5, 1.0))
        
        withdrawal_mean = safe_mean(daily_withdrawal_amounts, 0.0)
        withdrawal_std = safe_stdev(daily_withdrawal_amounts, max(withdrawal_mean * 0.5, 100.0))
        
        level_5_mean = safe_mean(daily_level_5_counts, 0.0)
        level_5_std = safe_stdev(daily_level_5_counts, max(level_5_mean * 0.5, 1.0))
        
        logger.debug(
            f"Dynamic baseline calculated from {days} days: "
            f"deposits={deposit_mean:.1f}±{deposit_std:.1f}, "
            f"withdrawals={withdrawal_mean:.1f}±{withdrawal_std:.1f}"
        )
        
        return {
            # Pending withdrawals - use current as baseline if no history
            "pending_withdrawals_mean": float(pending_count) or 1.0,
            "pending_withdrawals_std": max(float(pending_count) * 0.5, 1.0),
            # Withdrawal amounts from history
            "withdrawal_amount_mean": withdrawal_mean,
            "withdrawal_amount_std": withdrawal_std,
            # Rejection rate - keep reasonable default
            "rejection_rate_mean": 2.0,
            "rejection_rate_std": 2.0,
            # Deposit count from history
            "deposit_count_mean": deposit_mean,
            "deposit_count_std": deposit_std,
            # Level 5 from history
            "level_5_count_mean": level_5_mean,
            "level_5_count_std": level_5_std,
            # System liabilities - use current as baseline
            "system_liabilities_mean": system_liabilities or 1000.0,
            "system_liabilities_std": max(system_liabilities * 0.3, 1000.0),
        }

    async def _get_withdrawals_in_period(
        self, start: datetime, end: datetime
    ) -> list[Transaction]:
        """Get withdrawals in time period."""
        # Convert to naive datetime for Transaction model (TIMESTAMP WITHOUT TIME ZONE)
        start_naive = start.replace(tzinfo=None) if start.tzinfo else start
        end_naive = end.replace(tzinfo=None) if end.tzinfo else end
        
        stmt = (
            select(Transaction)
            .where(Transaction.type == TransactionType.WITHDRAWAL.value)
            .where(Transaction.created_at >= start_naive)
            .where(Transaction.created_at < end_naive)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_deposits_in_period(
        self, start: datetime, end: datetime
    ) -> list[Deposit]:
        """Get deposits in time period."""
        deposits = await self.deposit_repo.find_by(
            status=TransactionStatus.CONFIRMED.value,
        )
        if not deposits:
            return []

        return [
            d
            for d in deposits
            if d.created_at >= start and d.created_at < end
        ]

    async def _get_total_user_balance(self) -> Decimal:
        """Get total user balance."""
        stmt = select(func.sum(self.user_repo.model.balance))
        result = await self.session.execute(stmt)
        total = result.scalar() or Decimal("0")
        return total

    async def _get_total_confirmed_deposits(self) -> Decimal:
        """Get total confirmed deposits."""
        deposits = await self.deposit_repo.find_by(
            status=TransactionStatus.CONFIRMED.value,
        )
        if not deposits:
            return Decimal("0")

        return sum(d.amount for d in deposits)

    async def _get_total_confirmed_withdrawals(self) -> Decimal:
        """Get total confirmed withdrawals."""
        withdrawals = await self.transaction_repo.find_by(
            type=TransactionType.WITHDRAWAL.value,
            status=TransactionStatus.CONFIRMED.value,
        )
        if not withdrawals:
            return Decimal("0")

        return sum(Decimal(str(w.amount)) for w in withdrawals)

    async def _get_referral_earnings_last_day(
        self, day_ago: datetime
    ) -> Decimal:
        """Get referral earnings in last day."""
        # Simplified - would need referral_earnings table
        return Decimal("0")



