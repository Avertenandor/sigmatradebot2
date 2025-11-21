"""
AdminAction model.

Audit logging for admin actions with details and IP tracking.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.user import User


class AdminAction(Base):
    """
    AdminAction entity.

    Audit log for admin actions:
    - Action type tracking (ADMIN_CREATED, USER_BLOCKED, etc.)
    - Target user tracking (nullable)
    - IP address logging
    - JSON details for flexible data storage
    - Timestamp indexing for queries

    Attributes:
        id: Primary key
        admin_id: Admin who performed action (FK to admins)
        action_type: Type of action (enum string)
        target_user_id: Target user ID (nullable, FK to users)
        details: Action details (JSON, nullable)
        ip_address: Client IP address (PostgreSQL INET)
        created_at: Action timestamp (indexed)
    """

    __tablename__ = "admin_actions"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # Admin relationship
    admin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admins.id"), nullable=False, index=True
    )

    # Action details
    action_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )

    # Target user (nullable for actions not targeting users)
    target_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )

    # Additional details (JSON)
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )

    # IP address (PostgreSQL INET type)
    ip_address: Mapped[str | None] = mapped_column(
        INET, nullable=True
    )

    # R18-4: Immutable audit log flag
    is_immutable: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        server_default="false",
    )  # Set to True after N days to prevent modifications

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    # Relationships
    admin: Mapped["Admin"] = relationship(
        "Admin", lazy="joined"
    )

    target_user: Mapped[Optional["User"]] = relationship(
        "User", lazy="joined", foreign_keys=[target_user_id]
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"AdminAction(id={self.id}, "
            f"admin_id={self.admin_id}, "
            f"action_type={self.action_type!r})"
        )


# Composite index for admin actions queries
Index(
    "idx_admin_action_admin_created",
    AdminAction.admin_id,
    AdminAction.created_at,
)

