"""
FinancialPasswordRecovery model.

Tracks financial password recovery requests with video verification.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.user import User


class FinancialPasswordRecovery(Base):
    """
    FinancialPasswordRecovery entity.

    Manages password recovery process:
    - Video verification requirement
    - Admin approval workflow
    - User earnings blocked during recovery

    Status flow: pending → in_review → approved/rejected → sent

    Attributes:
        id: Primary key
        user_id: User requesting recovery
        status: Recovery status
        video_required: Video verification required
        video_verified: Video verification completed
    reason: User-provided recovery reason
    processed_by_admin_id: Admin who processed request
        processed_at: Processing timestamp
        admin_comment: Admin notes
        created_at: Request creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "financial_password_recovery"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # User
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )

    # User reason
    reason: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )

    # Video verification
    video_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    video_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Admin processing
    processed_by_admin_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admins.id"), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    admin_comment: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Audit timestamps
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
    user: Mapped["User"] = relationship("User", lazy="joined")
    processed_by_admin: Mapped[Optional["Admin"]] = relationship(
        "Admin", lazy="joined"
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"FinancialPasswordRecovery(id={self.id}, "
            f"user_id={self.user_id}, "
            f"status={self.status!r})"
        )
