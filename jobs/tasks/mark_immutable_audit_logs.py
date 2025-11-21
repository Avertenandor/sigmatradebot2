"""
R18-4: Task to mark old admin actions as immutable.

Runs periodically to mark admin actions older than N days as immutable,
preventing future modifications.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import dramatiq
from loguru import logger
from sqlalchemy import select, update

from app.config.database import async_session_maker
from app.config.settings import settings
from app.models.admin_action import AdminAction


@dramatiq.actor(max_retries=3, time_limit=60_000)  # 1 min timeout
def mark_immutable_audit_logs() -> dict:
    """
    Mark old admin actions as immutable.

    R18-4: Marks actions older than audit_log_immutable_after_days as immutable.

    Returns:
        Dict with marked count
    """
    logger.info("Starting immutable audit log marking...")

    try:
        # Run async code
        result = asyncio.run(_mark_immutable_async())

        logger.info(
            f"R18-4: Immutable audit log marking complete: "
            f"{result['marked']} actions marked as immutable"
        )

        return result

    except Exception as e:
        logger.exception(f"R18-4: Failed to mark immutable audit logs: {e}")
        return {"marked": 0}


async def _mark_immutable_async() -> dict:
    """
    Async implementation of marking immutable audit logs.

    Returns:
        Dict with marked count
    """
    async with async_session_maker() as session:
        try:
            cutoff_date = datetime.now(UTC) - timedelta(
                days=settings.audit_log_immutable_after_days
            )

            # Find actions that should be immutable but aren't yet
            stmt = (
                select(AdminAction)
                .where(AdminAction.created_at < cutoff_date)
                .where(AdminAction.is_immutable == False)  # noqa: E712
            )

            result = await session.execute(stmt)
            actions_to_mark = list(result.scalars().all())

            if not actions_to_mark:
                logger.debug("No admin actions to mark as immutable")
                return {"marked": 0}

            # Mark as immutable
            action_ids = [action.id for action in actions_to_mark]
            update_stmt = (
                update(AdminAction)
                .where(AdminAction.id.in_(action_ids))
                .values(is_immutable=True)
            )

            await session.execute(update_stmt)
            await session.commit()

            logger.info(
                f"R18-4: Marked {len(actions_to_mark)} admin actions as immutable "
                f"(older than {settings.audit_log_immutable_after_days} days)"
            )

            return {"marked": len(actions_to_mark)}

        except Exception as e:
            await session.rollback()
            logger.error(f"R18-4: Failed to mark immutable audit logs: {e}")
            raise

