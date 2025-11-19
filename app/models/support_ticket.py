"""
SupportTicket model.

Represents user support tickets with admin assignment.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import SupportTicketStatus

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.support_message import SupportMessage
    from app.models.user import User


class SupportTicket(Base):
    """
    SupportTicket entity.

    Represents a support ticket:
    - User's support request
    - Category and status tracking
    - Admin assignment
    - Message threading

    Attributes:
        id: Primary key
        user_id: User who created ticket
        category: Ticket category
        status: Current status
        assigned_admin_id: Assigned admin (optional)
        last_user_message_at: Last user message timestamp
        last_admin_message_at: Last admin message timestamp
        created_at: Ticket creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "support_tickets"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # User (nullable for guest tickets)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    
    # Telegram ID for guest tickets (when user_id is None)
    telegram_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )

    # Category & Status
    category: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SupportTicketStatus.OPEN.value,
        index=True,
    )

    # Admin assignment
    assigned_admin_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admins.id"), nullable=True, index=True
    )

    # Activity tracking
    last_user_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_admin_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", lazy="joined")
    assigned_admin: Mapped[Optional["Admin"]] = relationship(
        "Admin", lazy="joined"
    )
    messages: Mapped[list["SupportMessage"]] = relationship(
        "SupportMessage",
        back_populates="ticket",
        lazy="selectin",
        order_by="SupportMessage.created_at",
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"SupportTicket(id={self.id}, "
            f"user_id={self.user_id}, "
            f"status={self.status!r})"
        )
