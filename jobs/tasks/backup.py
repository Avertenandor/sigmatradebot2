"""Database backup task."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from app.config.settings import settings


async def backup_database() -> None:
    """
    Backup PostgreSQL database.

    Creates pg_dump backup with retention policy.
    """
    # Note: Backup settings should be configured via environment variables
    # or system settings service. For now, backup is always enabled.

    # Parse database URL to extract connection details
    from urllib.parse import urlparse

    parsed = urlparse(
        settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )

    db_host = parsed.hostname or "localhost"
    db_port = parsed.port or 5432
    db_user = parsed.username or "postgres"
    db_password = parsed.password or ""
    db_name = parsed.path.lstrip("/") if parsed.path else "sigmatrade"

    try:
        # Create backup directory
        backup_dir = Path("./backups")
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate backup filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"backup_{timestamp}.sql"

        logger.info(f"Starting database backup to {backup_file}")

        # Build pg_dump command
        cmd = [
            "pg_dump",
            "-h",
            db_host,
            "-p",
            str(db_port),
            "-U",
            db_user,
            "-d",
            db_name,
            "-F",
            "c",  # Custom format (compressed)
            "-f",
            str(backup_file),
        ]

        # Set password via environment
        env = {"PGPASSWORD": db_password}

        # Run pg_dump
        process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"Backup failed: {stderr.decode()}")
            return

        logger.success(f"Database backup completed: {backup_file}")

        # Cleanup old backups (keep last 30 days)
        await _cleanup_old_backups(backup_dir, retention_days=30)

    except Exception as e:
        logger.error(f"Backup error: {e}")


async def _cleanup_old_backups(backup_dir: Path, retention_days: int) -> None:
    """Clean up old backup files."""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        for backup_file in backup_dir.glob("backup_*.sql"):
            file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)

            if file_time < cutoff_date:
                backup_file.unlink()
                logger.info(f"Deleted old backup: {backup_file.name}")

    except Exception as e:
        logger.error(f"Backup cleanup error: {e}")
