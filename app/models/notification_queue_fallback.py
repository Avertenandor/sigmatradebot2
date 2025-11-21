"""
NotificationQueueFallback model.

R11-3: PostgreSQL fallback for notification queue when Redis is unavailable.
Stores pending notifications in PostgreSQL for later processing.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class NotificationQueueFallback(Base):
    """
    NotificationQueueFallback entity.

    R11-3: Stores notifications in PostgreSQL when Redis is unavailable.

    Workflow:
    1. NotificationService writes to this table when Redis is down
    2. Worker task polls this table every 5 seconds
    3. Notifications are sent and marked as processed
    4. When Redis recovers, remaining notifications are migrated back

    Attributes:
        id: Primary key
        user_id: User ID (FK to users)
        notification_type: Type of notification
        payload: JSON payload with notification data
        priority: Priority level (higher = more important)
        created_at: When notification was queued
        processed_at: When notification was sent (NULL = pending)
    """

    __tablename__ = "notification_queue_fallback"
    __table_args__ = (
        Index(
            "idx_notification_queue_processed_priority",
            "processed_at",
            "priority",
        ),
        Index(
            "idx_notification_queue_created",
            "created_at",
        ),
    )

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # User reference
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Notification details
    notification_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )  # Contains message, critical flag, etc.

    # Priority (higher = more important, default 0)
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        lazy="joined",
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"NotificationQueueFallback(id={self.id}, "
            f"user_id={self.user_id}, "
            f"type={self.notification_type!r}, "
            f"processed={self.processed_at is not None})"
        )

