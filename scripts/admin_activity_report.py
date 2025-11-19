#!/usr/bin/env python3
"""
Admin Activity Report Script.

Generates reports on admin actions for security monitoring.
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config.settings import settings
from app.models.admin_action import AdminAction


async def generate_admin_activity_report(
    days: int = 1,
    output_file: str | None = None,
) -> None:
    """
    Generate admin activity report.

    Args:
        days: Number of days to analyze (default: 1)
        output_file: Optional file path to save report
    """
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
    )
    SessionLocal = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with SessionLocal() as session:
            # Calculate date range
            end_date = datetime.now(UTC)
            start_date = end_date - timedelta(days=days)

            # 1. Total actions count
            total_stmt = select(func.count(AdminAction.id)).where(
                AdminAction.created_at >= start_date,
                AdminAction.created_at <= end_date,
            )
            total_result = await session.execute(total_stmt)
            total_actions = total_result.scalar() or 0

            # 2. Actions by type
            actions_by_type_stmt = (
                select(
                    AdminAction.action_type,
                    func.count(AdminAction.id).label("count"),
                )
                .where(
                    AdminAction.created_at >= start_date,
                    AdminAction.created_at <= end_date,
                )
                .group_by(AdminAction.action_type)
                .order_by(func.count(AdminAction.id).desc())
            )
            actions_by_type_result = await session.execute(
                actions_by_type_stmt
            )
            actions_by_type = actions_by_type_result.all()

            # 3. Bans and terminations
            ban_actions = [
                "USER_BLOCKED",
                "USER_TERMINATED",
                "ADMIN_TERMINATED",
            ]
            ban_stmt = (
                select(func.count(AdminAction.id))
                .where(
                    AdminAction.created_at >= start_date,
                    AdminAction.created_at <= end_date,
                    AdminAction.action_type.in_(ban_actions),
                )
            )
            ban_result = await session.execute(ban_stmt)
            total_bans = ban_result.scalar() or 0

            # 4. Withdrawal approvals
            withdrawal_stmt = (
                select(func.count(AdminAction.id))
                .where(
                    AdminAction.created_at >= start_date,
                    AdminAction.created_at <= end_date,
                    AdminAction.action_type == "WITHDRAWAL_APPROVED",
                )
            )
            withdrawal_result = await session.execute(withdrawal_stmt)
            total_withdrawals = withdrawal_result.scalar() or 0

            # 5. Most active admins
            active_admins_stmt = (
                select(
                    AdminAction.admin_id,
                    func.count(AdminAction.id).label("count"),
                )
                .where(
                    AdminAction.created_at >= start_date,
                    AdminAction.created_at <= end_date,
                )
                .group_by(AdminAction.admin_id)
                .order_by(func.count(AdminAction.id).desc())
                .limit(10)
            )
            active_admins_result = await session.execute(active_admins_stmt)
            active_admins = active_admins_result.all()

            # 6. Mass actions (N+ actions in short period)
            # Check for admins with >10 actions in last hour
            hour_ago = datetime.now(UTC) - timedelta(hours=1)
            mass_actions_stmt = (
                select(
                    AdminAction.admin_id,
                    AdminAction.action_type,
                    func.count(AdminAction.id).label("count"),
                )
                .where(AdminAction.created_at >= hour_ago)
                .group_by(AdminAction.admin_id, AdminAction.action_type)
                .having(func.count(AdminAction.id) > 10)
                .order_by(func.count(AdminAction.id).desc())
            )
            mass_actions_result = await session.execute(mass_actions_stmt)
            mass_actions = mass_actions_result.all()

            # Generate report
            report_lines = [
                "=" * 80,
                f"ADMIN ACTIVITY REPORT",
                f"Period: {start_date.strftime('%Y-%m-%d %H:%M')} - "
                f"{end_date.strftime('%Y-%m-%d %H:%M')}",
                f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC",
                "=" * 80,
                "",
                "SUMMARY:",
                f"  Total actions: {total_actions}",
                f"  Bans/Terminations: {total_bans}",
                f"  Withdrawal approvals: {total_withdrawals}",
                "",
                "ACTIONS BY TYPE:",
            ]

            for action_type, count in actions_by_type:
                report_lines.append(f"  {action_type}: {count}")

            report_lines.extend([
                "",
                "MOST ACTIVE ADMINS (Top 10):",
            ])

            for admin_id, count in active_admins:
                report_lines.append(f"  Admin ID {admin_id}: {count} actions")

            if mass_actions:
                report_lines.extend([
                    "",
                    "⚠️  MASS ACTIONS DETECTED (Last Hour):",
                    "  (Admins with >10 actions of same type)",
                ])
                for admin_id, action_type, count in mass_actions:
                    report_lines.append(
                        f"  Admin ID {admin_id}: {count} x {action_type}"
                    )

            report_lines.extend([
                "",
                "=" * 80,
            ])

            report_text = "\n".join(report_lines)

            # Output report
            if output_file:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(report_text)
                print(f"Report saved to: {output_file}")
            else:
                print(report_text)

    finally:
        await engine.dispose()


async def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate admin activity report"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days to analyze (default: 1)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: stdout)",
    )

    args = parser.parse_args()

    await generate_admin_activity_report(
        days=args.days,
        output_file=args.output,
    )


if __name__ == "__main__":
    asyncio.run(main())

