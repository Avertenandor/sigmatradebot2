"""
AdminSession model.

Tracks admin authentication sessions with expiration.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.admin import Admin


class AdminSession(Base):
    """
    AdminSession entity.

    Represents an admin authentication session:
    - Unique session token
    - Activity tracking
    - Auto-expiration (1 hour after last activity)
    - IP and user agent logging

    Attributes:
        id: Primary key
        admin_id: Foreign key to Admin
        session_token: Unique session identifier
        is_active: Session active status
        ip_address: Client IP address
        user_agent: Client user agent
        created_at: Session creation timestamp
        last_activity: Last activity timestamp
        expires_at: Session expiration timestamp
    """

    __tablename__ = "admin_sessions"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # Admin relationship
    admin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admins.id"), nullable=False, index=True
    )

    # Session Info
    session_token: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # Client Info
    ip_address: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Timestamps
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    admin: Mapped["Admin"] = relationship(
        "Admin", back_populates="sessions", lazy="joined"
    )

    # Properties

    @property
    def is_expired(self) -> bool:
        """
        Check if session is expired.

        Returns:
            True if session expired or inactive
        """
        if not self.is_active:
            return True

        if self.expires_at is None:
            return False

        return datetime.now(self.expires_at.tzinfo) > self.expires_at

    @property
    def remaining_time_minutes(self) -> float:
        """
        Get remaining session time in minutes.

        Returns:
            Minutes until expiration (0 if expired)
        """
        if self.is_expired:
            return 0.0

        if self.expires_at is None:
            return 60.0  # Default 1 hour

        remaining = self.expires_at - datetime.now(
            self.expires_at.tzinfo
        )
        return max(remaining.total_seconds() / 60, 0.0)

    @property
    def is_inactive(self) -> bool:
        """
        Check if session is inactive (no activity for 15 minutes).

        Returns:
            True if session is inactive (no activity > 15 minutes)
        """
        if not self.is_active:
            return True

        if self.last_activity is None:
            return True

        now = datetime.now(self.last_activity.tzinfo)
        inactivity_threshold = timedelta(minutes=15)
        time_since_activity = now - self.last_activity

        return time_since_activity > inactivity_threshold

    # Methods

    async def update_activity(self) -> None:
        """
        Update session activity.

        Updates last_activity and extends expires_at by 1 hour.
        """
        self.last_activity = datetime.now(datetime.now().astimezone().tzinfo)
        self.expires_at = self.last_activity + timedelta(hours=1)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"AdminSession(id={self.id}, "
            f"admin_id={self.admin_id}, "
            f"is_active={self.is_active})"
        )


# Composite indexes
Index(
    "idx_admin_session_admin_active",
    AdminSession.admin_id,
    AdminSession.is_active,
)
