"""
SupportTicket repository.

Data access layer for SupportTicket model.
"""


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.support_ticket import SupportTicket
from app.repositories.base import BaseRepository


class SupportTicketRepository(BaseRepository[SupportTicket]):
    """SupportTicket repository with specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize support ticket repository."""
        super().__init__(SupportTicket, session)

    async def get_by_user(
        self, user_id: int, status: str | None = None
    ) -> list[SupportTicket]:
        """
        Get tickets by user.

        Args:
            user_id: User ID
            status: Optional status filter

        Returns:
            List of tickets
        """
        filters: dict[str, int | str] = {"user_id": user_id}
        if status:
            filters["status"] = status

        return await self.find_by(**filters)

    async def get_with_messages(
        self, ticket_id: int
    ) -> SupportTicket | None:
        """
        Get ticket with messages loaded.

        Args:
            ticket_id: Ticket ID

        Returns:
            Ticket with messages or None
        """
        stmt = (
            select(SupportTicket)
            .where(SupportTicket.id == ticket_id)
            .options(selectinload(SupportTicket.messages))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_status(
        self, status: str
    ) -> list[SupportTicket]:
        """
        Get tickets by status.

        Args:
            status: Ticket status

        Returns:
            List of tickets
        """
        return await self.find_by(status=status)

    async def get_assigned_to_admin(
        self, admin_id: int
    ) -> list[SupportTicket]:
        """
        Get tickets assigned to admin.

        Args:
            admin_id: Admin ID

        Returns:
            List of assigned tickets
        """
        return await self.find_by(assigned_admin_id=admin_id)

    async def get_active_by_user(
        self, user_id: int
    ) -> SupportTicket | None:
        """
        Get active (open) ticket for user.

        Args:
            user_id: User ID

        Returns:
            Active ticket or None
        """
        from app.models.enums import SupportTicketStatus

        return await self.get_by(
            user_id=user_id, status=SupportTicketStatus.OPEN.value
        )

    async def get_active_by_telegram_id(
        self, telegram_id: int
    ) -> SupportTicket | None:
        """
        Get active (open) ticket for guest by telegram_id.

        Args:
            telegram_id: Telegram ID

        Returns:
            Active ticket or None
        """
        from app.models.enums import SupportTicketStatus
        from sqlalchemy import select

        stmt = (
            select(SupportTicket)
            .where(
                SupportTicket.telegram_id == telegram_id,
                SupportTicket.status == SupportTicketStatus.OPEN.value,
                SupportTicket.user_id.is_(None)  # Only guest tickets
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_telegram_id(
        self, telegram_id: int
    ) -> list[SupportTicket]:
        """
        Get all tickets for guest by telegram_id.

        Args:
            telegram_id: Telegram ID

        Returns:
            List of guest tickets (all statuses)
        """
        from sqlalchemy import select

        stmt = (
            select(SupportTicket)
            .where(
                SupportTicket.telegram_id == telegram_id,
                SupportTicket.user_id.is_(None)  # Only guest tickets
            )
            .order_by(SupportTicket.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())