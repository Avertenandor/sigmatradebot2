"""
Analytics Service.

Provides retention metrics (DAU/WAU/MAU) and cohort analysis.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.deposit import Deposit
from app.models.transaction import Transaction


class AnalyticsService:
    """Service for analytics and retention metrics."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize analytics service.

        Args:
            session: Database session
        """
        self.session = session

    async def get_retention_metrics(self) -> dict[str, Any]:
        """
        Get DAU/WAU/MAU retention metrics.

        Returns:
            Dict with dau, wau, mau counts and rates
        """
        now = datetime.now(UTC)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # DAU - users active in last 24 hours
        stmt = select(func.count(User.id)).where(
            User.last_active >= day_ago
        )
        result = await self.session.execute(stmt)
        dau = result.scalar() or 0

        # WAU - users active in last 7 days
        stmt = select(func.count(User.id)).where(
            User.last_active >= week_ago
        )
        result = await self.session.execute(stmt)
        wau = result.scalar() or 0

        # MAU - users active in last 30 days
        stmt = select(func.count(User.id)).where(
            User.last_active >= month_ago
        )
        result = await self.session.execute(stmt)
        mau = result.scalar() or 0

        # Total users
        stmt = select(func.count(User.id))
        result = await self.session.execute(stmt)
        total_users = result.scalar() or 0

        # Calculate rates
        dau_rate = (dau / total_users * 100) if total_users > 0 else 0
        wau_rate = (wau / total_users * 100) if total_users > 0 else 0
        mau_rate = (mau / total_users * 100) if total_users > 0 else 0

        # DAU/MAU ratio (stickiness)
        stickiness = (dau / mau * 100) if mau > 0 else 0

        return {
            "dau": dau,
            "wau": wau,
            "mau": mau,
            "total_users": total_users,
            "dau_rate": round(dau_rate, 1),
            "wau_rate": round(wau_rate, 1),
            "mau_rate": round(mau_rate, 1),
            "stickiness": round(stickiness, 1),  # DAU/MAU ratio
        }

    async def get_cohort_stats(self, days: int = 7) -> list[dict[str, Any]]:
        """
        Get cohort analysis by registration date.

        Args:
            days: Number of days to analyze

        Returns:
            List of cohort stats by day
        """
        now = datetime.now(UTC)
        cohorts = []

        for i in range(days):
            day_start = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)

            # Users registered on this day
            stmt = select(func.count(User.id)).where(
                and_(
                    User.created_at >= day_start,
                    User.created_at < day_end,
                )
            )
            result = await self.session.execute(stmt)
            registered = result.scalar() or 0

            # Of those, how many made a deposit
            stmt = select(func.count(func.distinct(Deposit.user_id))).where(
                and_(
                    Deposit.created_at >= day_start,
                    Deposit.created_at < day_end,
                    Deposit.status == "ACTIVE",
                )
            )
            result = await self.session.execute(stmt)
            deposited = result.scalar() or 0

            # Of those, how many are still active (last_active within 24h)
            stmt = select(func.count(User.id)).where(
                and_(
                    User.created_at >= day_start,
                    User.created_at < day_end,
                    User.last_active >= now - timedelta(days=1),
                )
            )
            result = await self.session.execute(stmt)
            still_active = result.scalar() or 0

            conversion_rate = (deposited / registered * 100) if registered > 0 else 0
            retention_rate = (still_active / registered * 100) if registered > 0 else 0

            cohorts.append({
                "date": day_start.strftime("%d.%m"),
                "registered": registered,
                "deposited": deposited,
                "still_active": still_active,
                "conversion_rate": round(conversion_rate, 1),
                "retention_rate": round(retention_rate, 1),
            })

        return cohorts

    async def get_churn_rate(self, days: int = 30) -> dict[str, Any]:
        """
        Calculate churn rate.

        Args:
            days: Period to calculate churn for

        Returns:
            Dict with churn metrics
        """
        now = datetime.now(UTC)
        period_start = now - timedelta(days=days)

        # Users active at start of period
        stmt = select(func.count(User.id)).where(
            and_(
                User.last_active >= period_start - timedelta(days=days),
                User.last_active < period_start,
            )
        )
        result = await self.session.execute(stmt)
        active_at_start = result.scalar() or 0

        # Of those, how many are still active
        stmt = select(func.count(User.id)).where(
            and_(
                User.last_active >= period_start - timedelta(days=days),
                User.last_active < period_start,
                User.last_active >= now - timedelta(days=days),
            )
        )
        result = await self.session.execute(stmt)
        still_active = result.scalar() or 0

        churned = active_at_start - still_active
        churn_rate = (churned / active_at_start * 100) if active_at_start > 0 else 0

        return {
            "period_days": days,
            "active_at_start": active_at_start,
            "still_active": still_active,
            "churned": churned,
            "churn_rate": round(churn_rate, 1),
        }

    async def get_average_deposit(self) -> dict[str, Any]:
        """
        Get average deposit metrics.

        Returns:
            Dict with average deposit stats
        """
        # Average deposit amount
        stmt = select(func.avg(Deposit.amount)).where(
            Deposit.status == "ACTIVE"
        )
        result = await self.session.execute(stmt)
        avg_deposit = result.scalar() or Decimal("0")

        # Total deposited
        stmt = select(func.sum(Deposit.amount)).where(
            Deposit.status == "ACTIVE"
        )
        result = await self.session.execute(stmt)
        total_deposited = result.scalar() or Decimal("0")

        # Users with deposits
        stmt = select(func.count(func.distinct(Deposit.user_id))).where(
            Deposit.status == "ACTIVE"
        )
        result = await self.session.execute(stmt)
        users_with_deposits = result.scalar() or 0

        # Total users
        stmt = select(func.count(User.id))
        result = await self.session.execute(stmt)
        total_users = result.scalar() or 0

        deposit_rate = (users_with_deposits / total_users * 100) if total_users > 0 else 0

        return {
            "avg_deposit": float(avg_deposit),
            "total_deposited": float(total_deposited),
            "users_with_deposits": users_with_deposits,
            "total_users": total_users,
            "deposit_rate": round(deposit_rate, 1),
        }

