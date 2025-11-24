"""
Deposit corridor history model.

Tracks changes to ROI corridors for each deposit level.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.admin import Admin


class DepositCorridorHistory(Base):
    """
    Deposit corridor history model.

    Tracks all changes to ROI corridor settings for deposit levels.
    Provides full audit trail of corridor modifications.
    """

    __tablename__ = "deposit_corridor_history"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # Level number (1-5)
    level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Mode: 'custom' (random from corridor) or 'equal' (fixed for all)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)

    # Corridor settings (for 'custom' mode)
    roi_min: Mapped[Decimal | None] = mapped_column(
        DECIMAL(5, 2), nullable=True
    )
    roi_max: Mapped[Decimal | None] = mapped_column(
        DECIMAL(5, 2), nullable=True
    )

    # Fixed rate (for 'equal' mode)
    roi_fixed: Mapped[Decimal | None] = mapped_column(
        DECIMAL(5, 2), nullable=True
    )

    # Optional human-readable reason/comment for the change
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Admin tracking
    changed_by_admin_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )

    # Timestamp
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    # Application scope: 'current' or 'next'
    applies_to: Mapped[str] = mapped_column(String(20), nullable=False)

    # Relationships
    changed_by: Mapped[Admin | None] = relationship(
        "Admin", foreign_keys=[changed_by_admin_id]
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<DepositCorridorHistory(id={self.id}, level={self.level}, "
            f"mode={self.mode}, applies_to={self.applies_to}, "
            f"changed_at={self.changed_at})>"
        )

