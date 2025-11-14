"""
Support service.

Manages support ticket system for users.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SupportSender, SupportStatus
from app.models.support_message import SupportMessage
from app.models.support_ticket import SupportTicket
from app.repositories.support_message_repository import (
    SupportMessageRepository,
)
from app.repositories.support_ticket_repository import (
    SupportTicketRepository,
)


class SupportService:
    """Support service for ticket management."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize support service."""
        self.session = session
        self.ticket_repo = SupportTicketRepository(session)
        self.message_repo = SupportMessageRepository(session)

    async def create_ticket(
        self,
        user_id: int,
        category: str,
        initial_message: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[Optional[SupportTicket], Optional[str]]:
        """
        Create new support ticket.

        Args:
            user_id: User ID
            category: Ticket category
            initial_message: Initial message text
            attachments: List of attachment dicts

        Returns:
            Tuple of (ticket, error_message)
        """
        # Check if user already has active ticket
        existing = await self.ticket_repo.get_active_by_user(user_id)

        if existing:
            return None, (
                "У вас уже есть активное обращение. "
                "Пожалуйста, дождитесь его закрытия."
            )

        # Create ticket
        ticket = await self.ticket_repo.create(
            user_id=user_id,
            category=category,
            status=SupportStatus.OPEN.value,
            last_user_message_at=datetime.utcnow(),
        )

        # Add initial message if provided
        if initial_message or attachments:
            await self.add_user_message(
                ticket_id=ticket.id,
                text=initial_message,
                attachments=attachments,
            )

        await self.session.commit()

        logger.info(
            "Support ticket created",
            extra={
                "ticket_id": ticket.id,
                "user_id": user_id,
                "category": category,
            },
        )

        return ticket, None

    async def add_user_message(
        self,
        ticket_id: int,
        text: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> SupportMessage:
        """
        Add user message to ticket.

        Args:
            ticket_id: Ticket ID
            text: Message text
            attachments: List of attachment dicts

        Returns:
            SupportMessage record
        """
        # Create message
        message = await self.message_repo.create(
            ticket_id=ticket_id,
            sender=SupportSender.USER.value,
            text=text,
            attachments=attachments,
        )

        # Update ticket timestamp and reset to open
        await self.ticket_repo.update(
            ticket_id,
            last_user_message_at=datetime.utcnow(),
            status=SupportStatus.OPEN.value,
        )

        await self.session.flush()

        return message

    async def add_admin_message(
        self,
        ticket_id: int,
        admin_id: int,
        text: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> SupportMessage:
        """
        Add admin message to ticket.

        Args:
            ticket_id: Ticket ID
            admin_id: Admin ID
            text: Message text
            attachments: List of attachment dicts

        Returns:
            SupportMessage record
        """
        # Create message
        message = await self.message_repo.create(
            ticket_id=ticket_id,
            sender=SupportSender.ADMIN.value,
            admin_id=admin_id,
            text=text,
            attachments=attachments,
        )

        # Update ticket timestamp and mark as answered
        await self.ticket_repo.update(
            ticket_id,
            last_admin_message_at=datetime.utcnow(),
            status=SupportStatus.ANSWERED.value,
        )

        await self.session.flush()

        return message

    async def add_system_message(
        self, ticket_id: int, text: str
    ) -> SupportMessage:
        """
        Add system message to ticket.

        Args:
            ticket_id: Ticket ID
            text: Message text

        Returns:
            SupportMessage record
        """
        message = await self.message_repo.create(
            ticket_id=ticket_id,
            sender=SupportSender.SYSTEM.value,
            text=text,
        )

        await self.session.flush()

        return message

    async def assign_to_admin(
        self, ticket_id: int, admin_id: int
    ) -> None:
        """
        Assign ticket to admin.

        Args:
            ticket_id: Ticket ID
            admin_id: Admin ID
        """
        await self.ticket_repo.update(
            ticket_id,
            assigned_admin_id=admin_id,
            status=SupportStatus.IN_PROGRESS.value,
        )

        await self.session.flush()

        logger.info(
            "Ticket assigned to admin",
            extra={"ticket_id": ticket_id, "admin_id": admin_id},
        )

    async def close_ticket(self, ticket_id: int) -> None:
        """
        Close ticket.

        Args:
            ticket_id: Ticket ID
        """
        await self.ticket_repo.update(
            ticket_id, status=SupportStatus.CLOSED.value
        )

        await self.session.flush()

        logger.info("Ticket closed", extra={"ticket_id": ticket_id})

    async def reopen_ticket(self, ticket_id: int) -> None:
        """
        Reopen closed ticket.

        Args:
            ticket_id: Ticket ID
        """
        await self.ticket_repo.update(
            ticket_id, status=SupportStatus.OPEN.value
        )

        await self.session.flush()

        logger.info("Ticket reopened", extra={"ticket_id": ticket_id})

    async def list_open_tickets(self) -> List[SupportTicket]:
        """
        List all open tickets (for admin).

        Returns:
            List of open/in_progress/answered tickets
        """
        stmt = (
            select(SupportTicket)
            .where(
                or_(
                    SupportTicket.status == SupportStatus.OPEN.value,
                    SupportTicket.status == SupportStatus.IN_PROGRESS.value,
                    SupportTicket.status == SupportStatus.ANSWERED.value,
                )
            )
            .order_by(SupportTicket.created_at.desc())
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_ticket_by_id(
        self, ticket_id: int
    ) -> Optional[SupportTicket]:
        """
        Get ticket by ID with messages.

        Args:
            ticket_id: Ticket ID

        Returns:
            SupportTicket or None
        """
        ticket = await self.ticket_repo.get_by_id(ticket_id)

        if ticket:
            # Load messages separately and sort
            messages = await self.message_repo.find_by(
                ticket_id=ticket_id
            )
            messages.sort(key=lambda m: m.created_at)
            ticket.messages = messages  # type: ignore

        return ticket

    async def get_user_tickets(
        self, user_id: int
    ) -> List[SupportTicket]:
        """
        Get all tickets for user.

        Args:
            user_id: User ID

        Returns:
            List of user's tickets
        """
        return await self.ticket_repo.get_by_user(user_id)

    async def get_user_active_ticket(
        self, user_id: int
    ) -> Optional[SupportTicket]:
        """
        Get user's active ticket if exists.

        Args:
            user_id: User ID

        Returns:
            Active ticket or None
        """
        return await self.ticket_repo.get_active_by_user(user_id)
