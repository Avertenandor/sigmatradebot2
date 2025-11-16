"""
Referral model.

Represents referral relationships between users.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Referral(Base):
    """Referral model - multi-level referral relationships."""

    __tablename__ = "referrals"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Referrer (who invited)
    referrer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Referral (who was invited)
    referral_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Referral level (1-3)
    level: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )  # 1 = direct, 2 = second level, 3 = third level

    # Total earnings from this referral
    total_earned: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8), nullable=False, default=Decimal("0")
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
        nullable=False
    )

    # Relationships
    referrer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[referrer_id],
    )
    referral: Mapped["User"] = relationship(
        "User",
        foreign_keys=[referral_id],
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Referral(id={self.id}, referrer_id={self.referrer_id}, "
            f"referral_id={self.referral_id}, level={self.level})>"
        )
