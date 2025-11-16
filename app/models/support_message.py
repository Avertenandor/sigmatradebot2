"""
SupportMessage model.

Represents individual messages in support tickets.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.support_ticket import SupportTicket


class SupportMessage(Base):
    """
    SupportMessage entity.

    Represents a message in support ticket:
    - Text message
    - Multimedia attachments
    - Sender tracking (user/admin/system)

    Attributes:
        id: Primary key
        ticket_id: Foreign key to SupportTicket
        sender: Message sender type
        admin_id: Admin ID if sender is admin
        text: Message text (optional if only attachments)
        attachments: Multimedia attachments (JSON)
        created_at: Message timestamp
    """

    __tablename__ = "support_messages"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # Ticket
    ticket_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("support_tickets.id"),
        nullable=False,
        index=True,
    )

    # Sender
    sender: Mapped[str] = mapped_column(String(10), nullable=False)

    # Admin ID (if sender is admin)
    admin_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # Message content
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Attachments (JSON array)
    # Format: [{type: 'photo'|'voice'|'audio'|'document',
    #           file_id: str, caption?: str}]
    attachments: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )

    # Relationships
    ticket: Mapped["SupportTicket"] = relationship(
        "SupportTicket", back_populates="messages", lazy="joined"
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"SupportMessage(id={self.id}, "
            f"ticket_id={self.ticket_id}, "
            f"sender={self.sender!r})"
        )
