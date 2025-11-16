"""
SupportMessage model.

Represents individual messages in support tickets.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import DateTime, Index, Integer, String, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import SupportSender

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
    admin_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    # Message content
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Attachments (JSON array)
    # Format: [{type: 'photo'|'voice'|'audio'|'document',
    #           file_id: str, caption?: str}]
    attachments: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON, nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
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
