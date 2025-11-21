"""
Deposit level version model.

R17-1, R17-2: Versions deposit conditions and tracks level availability.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DECIMAL,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.deposit import Deposit


class DepositLevelVersion(Base):
    """
    Deposit level version model.

    R17-1: Stores versioned deposit conditions.
    R17-2: Tracks level availability (is_active flag).

    Each deposit references a specific version to ensure
    old deposits continue with their original conditions.
    """

    __tablename__ = "deposit_level_versions"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # Level number (1-5)
    level_number: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )

    # Deposit conditions
    amount: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2), nullable=False
    )
    roi_percent: Mapped[Decimal] = mapped_column(
        DECIMAL(5, 2), nullable=False
    )
    roi_cap_percent: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # e.g., 500 for 500%

    # Version tracking
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, index=True
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    effective_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # R17-2: Level availability
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )

    # Admin tracking
    created_by_admin_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admins.id"), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    created_by: Mapped["Admin | None"] = relationship(
        "Admin", foreign_keys=[created_by_admin_id]
    )
    deposits: Mapped[list["Deposit"]] = relationship(
        "Deposit", back_populates="deposit_version"
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<DepositLevelVersion(id={self.id}, level={self.level_number}, "
            f"version={self.version}, amount={self.amount}, "
            f"is_active={self.is_active})>"
        )

