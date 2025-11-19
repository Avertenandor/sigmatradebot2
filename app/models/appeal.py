"""
Appeal model.

Tracks user appeals for blocked accounts.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppealStatus(str):
    """Appeal status types."""

    PENDING = "pending"  # Ожидает рассмотрения
    UNDER_REVIEW = "under_review"  # На рассмотрении
    APPROVED = "approved"  # Одобрена
    REJECTED = "rejected"  # Отклонена


class Appeal(Base):
    """
    Appeal entity.

    Represents a user appeal for a blocked account:
    - User who submitted appeal
    - Blacklist entry related to appeal
    - Appeal text
    - Status and review information
    - Admin who reviewed (if reviewed)

    Attributes:
        id: Primary key
        user_id: User who submitted appeal
        blacklist_id: Related blacklist entry ID
        appeal_text: Appeal text content
        status: Appeal status (pending, under_review, approved, rejected)
        reviewed_by_admin_id: Admin ID who reviewed appeal (if reviewed)
        review_notes: Admin review notes (optional)
        reviewed_at: Review timestamp (if reviewed)
        created_at: Appeal submission timestamp
    """

    __tablename__ = "appeals"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # User who submitted appeal
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Related blacklist entry
    blacklist_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("blacklist.id", ondelete="CASCADE"), nullable=False
    )

    # Appeal text
    appeal_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(50), default=AppealStatus.PENDING, nullable=False
    )

    # Review information (optional, set when reviewed)
    reviewed_by_admin_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )

    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Appeal(id={self.id}, user_id={self.user_id}, "
            f"status={self.status})>"
        )
