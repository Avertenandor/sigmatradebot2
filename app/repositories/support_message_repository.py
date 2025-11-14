"""
SupportMessage repository.

Data access layer for SupportMessage model.
"""

from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.support_message import SupportMessage
from app.repositories.base import BaseRepository


class SupportMessageRepository(
    BaseRepository[SupportMessage]
):
    """SupportMessage repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize support message repository."""
        super().__init__(SupportMessage, session)

    async def get_by_ticket(
        self, ticket_id: int
    ) -> List[SupportMessage]:
        """
        Get messages by ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            List of messages ordered by creation time
        """
        messages = await self.find_by(ticket_id=ticket_id)
        # Sort by created_at
        return sorted(messages, key=lambda m: m.created_at)

    async def get_by_sender(
        self, ticket_id: int, sender: str
    ) -> List[SupportMessage]:
        """
        Get messages by ticket and sender.

        Args:
            ticket_id: Ticket ID
            sender: Sender type (user/admin/system)

        Returns:
            List of messages
        """
        return await self.find_by(
            ticket_id=ticket_id, sender=sender
        )
