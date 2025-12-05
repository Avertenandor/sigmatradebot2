"""
UserAction model.

Audit logging for user actions with auto-cleanup after 7 days.
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserAction(Base):
    """
    UserAction entity.

    Audit log for user actions:
    - Action tracking
    - IP address logging
    - TTL: 7 days (auto-deleted by cleanup job)

    Attributes:
        id: Primary key
        user_id: User who performed action (nullable)
        action_type: Type of action
        details: Action details (JSON)
        ip_address: Client IP address (PostgreSQL INET)
        created_at: Action timestamp (indexed)
    """

    __tablename__ = "user_actions"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # User (nullable for anonymous actions)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )

    # Action details
    action_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )

    # IP address (PostgreSQL INET type)
    ip_address: Mapped[str | None] = mapped_column(
        INET, nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User", lazy="joined"
    )

    # Properties

    @property
    def should_be_deleted(self) -> bool:
        """
        Check if action should be deleted (older than 7 days).

        Returns:
            True if action is older than 7 days
        """
        seven_days_ago = datetime.now(
            self.created_at.tzinfo
        ) - timedelta(days=7)
        return self.created_at < seven_days_ago

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"UserAction(id={self.id}, "
            f"user_id={self.user_id}, "
            f"action_type={self.action_type!r})"
        )


# Index on created_at for cleanup job
Index("idx_user_action_created", UserAction.created_at)
