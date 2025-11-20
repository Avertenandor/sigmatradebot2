"""
Admin notification utilities.

Provides async helpers for sending security event notifications to admins.
"""

import asyncio
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger


async def notify_security_event(
    event_type: str,
    details: str,
    priority: str = "high",
) -> None:
    """
    Send security event notification to super admins.

    Args:
        event_type: Type of security event (e.g., "Admin Login Brute Force")
        details: Detailed message
        priority: "critical" | "high" | "medium"
    """
    try:
        message = f"🚨 {event_type}\n\n{details}"

        # Get script path
        script_path = Path(__file__).parent.parent.parent / "scripts" / "notify_admin.py"

        if not script_path.exists():
            logger.warning(
                f"notify_admin.py not found at {script_path}, "
                "skipping notification"
            )
            return

        # Build command
        cmd = ["python", str(script_path), message]
        if priority == "critical":
            cmd.append("--critical")

        # Run in subprocess (non-blocking)
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Don't wait for completion (fire and forget)
        logger.debug(
            f"Security notification sent: {event_type} (priority: {priority})"
        )

    except Exception as e:
        logger.error(f"Failed to send security notification: {e}")

