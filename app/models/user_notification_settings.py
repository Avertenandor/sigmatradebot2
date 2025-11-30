"""
User notification settings model.

Stores user preferences for notifications (deposits, withdrawals, marketing).
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserNotificationSettings(Base):
    """
    User notification settings.

    Stores user preferences for different types of notifications.
    """

    __tablename__ = "user_notification_settings"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # User reference
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Notification preferences
    deposit_notifications: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    withdrawal_notifications: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    roi_notifications: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    marketing_notifications: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="notification_settings",
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<UserNotificationSettings(id={self.id}, user_id={self.user_id}, "
            f"deposit={self.deposit_notifications}, "
            f"withdrawal={self.withdrawal_notifications}, "
            f"roi={self.roi_notifications}, "
            f"marketing={self.marketing_notifications})>"
        )
