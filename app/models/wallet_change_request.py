"""
WalletChangeRequest model.

Tracks admin-initiated wallet change requests with approval workflow.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import WalletChangeStatus, WalletChangeType

if TYPE_CHECKING:
    from app.models.admin import Admin


class WalletChangeRequest(Base):
    """
    WalletChangeRequest entity.

    Manages wallet change approval workflow:
    - System deposit wallet changes
    - Payout withdrawal wallet changes
    - Two-step approval (initiate + approve)
    - Application tracking

    Status flow: pending → approved → applied (or rejected)

    Attributes:
        id: Primary key
        type: Change type (system_deposit/payout_withdrawal)
        new_address: New wallet address
        secret_ref: Secret manager reference (optional)
        initiated_by_admin_id: Admin who initiated
        approved_by_admin_id: Admin who approved (optional)
        status: Request status
        reason: Change reason (optional)
        created_at: Initiation timestamp
        approved_at: Approval timestamp
        applied_at: Application timestamp
    """

    __tablename__ = "wallet_change_requests"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # Request details
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    new_address: Mapped[str] = mapped_column(
        String(42), nullable=False
    )
    secret_ref: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Admin workflow
    initiated_by_admin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admins.id"), nullable=False, index=True
    )
    approved_by_admin_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admins.id"), nullable=True
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=WalletChangeStatus.PENDING.value,
        index=True,
    )

    # Additional info
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    initiated_by: Mapped["Admin"] = relationship(
        "Admin",
        foreign_keys=[initiated_by_admin_id],
        back_populates="initiated_wallet_changes",
        lazy="joined",
    )
    approved_by: Mapped[Optional["Admin"]] = relationship(
        "Admin",
        foreign_keys=[approved_by_admin_id],
        back_populates="approved_wallet_changes",
        lazy="joined",
    )

    # Properties

    @property
    def is_pending(self) -> bool:
        """Check if request is pending."""
        return self.status == WalletChangeStatus.PENDING.value

    @property
    def is_approved(self) -> bool:
        """Check if request is approved."""
        return self.status == WalletChangeStatus.APPROVED.value

    @property
    def is_applied(self) -> bool:
        """Check if request is applied."""
        return self.status == WalletChangeStatus.APPLIED.value

    @property
    def is_rejected(self) -> bool:
        """Check if request is rejected."""
        return self.status == WalletChangeStatus.REJECTED.value

    @property
    def is_active(self) -> bool:
        """Check if request is active (not applied/rejected)."""
        return self.status in (
            WalletChangeStatus.PENDING.value,
            WalletChangeStatus.APPROVED.value,
        )

    @property
    def type_display(self) -> str:
        """Get formatted type name."""
        type_map = {
            WalletChangeType.SYSTEM_DEPOSIT.value: "System Deposit",
            WalletChangeType.PAYOUT_WITHDRAWAL.value: "Payout Withdrawal",
        }
        return type_map.get(self.type, self.type)

    @property
    def status_display(self) -> str:
        """Get formatted status name."""
        status_map = {
            WalletChangeStatus.PENDING.value: "Pending",
            WalletChangeStatus.APPROVED.value: "Approved",
            WalletChangeStatus.APPLIED.value: "Applied",
            WalletChangeStatus.REJECTED.value: "Rejected",
        }
        return status_map.get(self.status, self.status)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"WalletChangeRequest(id={self.id}, "
            f"type={self.type!r}, "
            f"status={self.status!r})"
        )
