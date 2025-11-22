"""
AdminActionEscrow model.

R18-4: Dual control (four-eyes principle) for critical admin operations.

Stores pending approvals that require two admins:
- First admin initiates the action
- Second admin must approve before execution
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    text,
)
from sqlalchemy.sql import func as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.transaction import Transaction


class AdminActionEscrow(Base):
    """
    AdminActionEscrow entity.

    R18-4: Implements dual control for critical operations.

    Workflow:
    1. First admin initiates action (creates escrow record)
    2. Second admin reviews and approves/rejects
    3. Action is executed only after second approval

    Supported operations:
    - Large withdrawals (>$1000)
    - Balance adjustments
    - Critical config changes
    """

    __tablename__ = "admin_action_escrows"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # Operation details
    operation_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # WITHDRAWAL_APPROVAL, BALANCE_ADJUSTMENT, etc.

    # Target resource
    target_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )  # withdrawal_id, user_id, etc.

    # Operation data (JSON)
    operation_data: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )  # amount, reason, etc.

    # Initiator (first admin)
    initiator_admin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admins.id"), nullable=False, index=True
    )

    # Approver (second admin, nullable until approved)
    approver_admin_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admins.id"), nullable=True, index=True
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", server_default="PENDING"
    )  # PENDING, APPROVED, REJECTED, EXPIRED

    # Reason for rejection (if rejected)
    rejection_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        nullable=False,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )  # Auto-expire after 24 hours

    # Relationships
    initiator: Mapped["Admin"] = relationship(
        "Admin",
        foreign_keys=[initiator_admin_id],
        lazy="joined",
    )

    approver: Mapped["Admin | None"] = relationship(
        "Admin",
        foreign_keys=[approver_admin_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"AdminActionEscrow(id={self.id}, "
            f"operation_type={self.operation_type!r}, "
            f"status={self.status!r})"
        )

