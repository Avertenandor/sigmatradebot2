"""Cleanup task for logs and orphaned data."""

from datetime import datetime, timedelta
from pathlib import Path

from app.database import async_session_maker
from loguru import logger


async def cleanup_logs_and_data() -> None:
    """
    Cleanup old logs and orphaned data.

    - Deletes old log files (>7 days)
    - Removes orphaned pending deposits (>24 hours)
    - Cleans up old sessions
    """
    try:
        # Cleanup log files
        await _cleanup_log_files()

        # Cleanup database
        await _cleanup_database()

        logger.info("Cleanup task completed")

    except Exception as e:
        logger.error(f"Cleanup task error: {e}")


async def _cleanup_log_files() -> None:
    """Delete old log files."""
    try:
        log_dir = Path("logs")

        if not log_dir.exists():
            return

        cutoff_date = datetime.utcnow() - timedelta(days=7)

        for log_file in log_dir.glob("*.log*"):
            if log_file.is_file():
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)

                if file_time < cutoff_date:
                    log_file.unlink()
                    logger.info(f"Deleted old log: {log_file.name}")

    except Exception as e:
        logger.error(f"Log cleanup error: {e}")


async def _cleanup_database() -> None:
    """Cleanup orphaned database records."""
    try:
        async with async_session_maker() as session:
            # Cleanup orphaned pending deposits (>24 hours old)
            from app.repositories.deposit_repository import DepositRepository

            deposit_repo = DepositRepository(session)

            cutoff_time = datetime.utcnow() - timedelta(hours=24)

            # Find old pending deposits
            deposits = await deposit_repo.get_pending_deposits()

            deleted_count = 0

            for deposit in deposits:
                if deposit.created_at < cutoff_time:
                    await deposit_repo.delete(deposit.id)
                    deleted_count += 1

            if deleted_count > 0:
                logger.info(
                    f"Deleted {deleted_count} orphaned pending deposits"
                )

            await session.commit()

    except Exception as e:
        logger.error(f"Database cleanup error: {e}")
