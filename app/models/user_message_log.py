"""
UserMessageLog model.

Stores last 500 text messages per user for admin monitoring.
Auto-cleanup keeps only recent messages.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserMessageLog(Base):
    """
    UserMessageLog entity.

    Stores user text messages for admin monitoring:
    - Last 500 messages per user (auto-cleanup)
    - Text content only (no buttons/callbacks)
    - Timestamp for ordering
    - Auto-cleanup by service

    Attributes:
        id: Primary key
        user_id: User FK (nullable for non-registered users)
        telegram_id: Telegram ID (always present)
        message_text: Message content
        created_at: Message timestamp (indexed)
    """

    __tablename__ = "user_message_logs"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # User (nullable for non-registered users)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )

    # Telegram ID (always present, indexed for queries)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )

    # Message content
    message_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User | None"] = relationship("User", lazy="select")

    # Indexes for efficient queries
    __table_args__ = (
        # Composite index for user + timestamp queries
        Index(
            "ix_user_message_logs_telegram_id_created_at",
            "telegram_id",
            "created_at",
        ),
        # Index for cleanup queries
        Index("ix_user_message_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<UserMessageLog(id={self.id}, "
            f"telegram_id={self.telegram_id}, "
            f"text='{self.message_text[:50]}...', "
            f"created_at={self.created_at})>"
        )

