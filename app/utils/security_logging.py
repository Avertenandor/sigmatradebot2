"""
Security logging utility.

Provides standardized security event logging with [SECURITY] prefix.
"""

from typing import Any

from loguru import logger


def log_security_event(event_type: str, details: dict[str, Any]) -> None:
    """
    Log security event with standardized format.

    Args:
        event_type: Type of security event (e.g., "User blocked", "Admin login failed")
        details: Dictionary with context (telegram_id, admin_id, reason, etc.)
    """
    logger.warning(f"[SECURITY] {event_type}", extra=details)

