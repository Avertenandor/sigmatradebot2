"""
Blacklist model.

Tracks banned users with reason and admin who banned them.
"""

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BlacklistActionType(str):
    """Blacklist action types."""

    REGISTRATION_DENIED = "registration_denied"  # Отказ в регистрации
    TERMINATED = "terminated"  # Терминация аккаунта
    BLOCKED = "blocked"  # Блокировка аккаунта (с возможностью апелляции)


class Blacklist(Base):
    """
    Blacklist entity.

    Represents a banned user:
    - Telegram ID of banned user
    - Action type (registration_denied, terminated, blocked)
    - Ban reason
    - Admin who banned them
    - Appeal deadline (for blocked users)

    Attributes:
        id: Primary key
        telegram_id: Banned user's Telegram ID
        action_type: Type of action (registration_denied, terminated, blocked)
        reason: Ban reason (optional)
        created_by_admin_id: Admin ID who created ban
        appeal_deadline: Deadline for appeal (blocked users, 3 days)
        created_at: Ban timestamp
        is_active: Whether the blacklist entry is active
    """

    __tablename__ = "blacklist"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # Banned user
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=False, nullable=True, index=True
    )

    # Wallet address (for wallet-based bans)
    wallet_address: Mapped[str | None] = mapped_column(
        String(42), nullable=True, index=True
    )

    # Action type
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=BlacklistActionType.REGISTRATION_DENIED,
        index=True
    )

    # Ban details
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Admin who banned (stored as int, no FK for simplicity)
    created_by_admin_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # Appeal deadline for blocked users (3 working days from creation)
    appeal_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Active status
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Blacklist(id={self.id}, telegram_id={self.telegram_id}, "
            f"wallet_address={self.wallet_address}, "
            f"action_type={self.action_type})"
        )
