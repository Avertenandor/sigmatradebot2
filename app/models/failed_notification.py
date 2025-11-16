"""
FailedNotification model (КРИТИЧНО - PART5).

Tracks failed notification attempts for retry and admin monitoring.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON as JSONB,
)
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FailedNotification(Base):
    """
    FailedNotification entity (КРИТИЧНО из PART5!).

    Tracks failed notification attempts:
    - User blocked bot
    - User deleted account
    - Telegram API errors
    - Retry mechanism support
    - Admin monitoring for critical notifications

    Attributes:
        id: Primary key
        user_telegram_id: Telegram ID (no FK - may not exist)
        notification_type: Type of notification
        message: Notification text
        metadata: Additional data (JSON)
        attempt_count: Number of retry attempts
        last_error: Last error message
        resolved: Successfully sent flag
        critical: Critical notification flag
        created_at: First attempt timestamp
        updated_at: Last update timestamp
        last_attempt_at: Last retry timestamp
        resolved_at: Resolution timestamp
    """

    __tablename__ = "failed_notifications"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # User (no FK - user may not exist or be deleted)
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )

    # Notification details
    notification_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata (JSON) - using notification_metadata to avoid
    # SQLAlchemy reserved word conflict
    notification_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    # Retry tracking
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Status flags
    resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"FailedNotification(id={self.id}, "
            f"user_telegram_id={self.user_telegram_id}, "
            f"type={self.notification_type!r}, "
            f"resolved={self.resolved})"
        )


# Critical indexes for PART5
Index(
    "idx_failed_notification_resolved_critical",
    FailedNotification.resolved,
    FailedNotification.critical,
)
Index(
    "idx_failed_notification_created",
    FailedNotification.created_at,
)
