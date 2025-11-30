"""
Cleanup Task.

Cleans up old data to maintain database performance.
"""

from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import delete

from app.config.database import async_session_maker
from app.models.admin_action import AdminAction


async def run_cleanup_task() -> None:
    """
    Clean up logs older than 30 days.
    """
    logger.info("Starting cleanup task...")
    
    cutoff_date = datetime.now(UTC) - timedelta(days=30)
    
    async with async_session_maker() as session:
        try:
            async with session.begin():
                # Delete old admin actions
                stmt = delete(AdminAction).where(AdminAction.created_at < cutoff_date)
                result = await session.execute(stmt)
                deleted_count = result.rowcount
            
            # Commit handled by context manager session.begin() or explicit commit if needed?
            # session.begin() handles commit on exit.
            
            logger.info(f"Cleanup completed. Deleted {deleted_count} old admin logs.")
            
        except Exception as e:
            logger.error(f"Cleanup task failed: {e}")
