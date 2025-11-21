"""
Admin model.

Represents bot administrators with role-based permissions.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.admin_session import AdminSession
    from app.models.wallet_change_request import WalletChangeRequest


class Admin(Base):
    """
    Admin entity.

    Represents a bot administrator with:
    - Telegram account info
    - Role-based permissions (admin, extended_admin, super_admin)
    - Master key for 2FA authentication
    - Self-referencing creator tracking

    Attributes:
        id: Primary key
        telegram_id: Unique Telegram admin ID
        username: Telegram username (optional)
        role: Admin role (admin/extended_admin/super_admin)
        master_key: Hashed master key for authentication
        created_by: ID of admin who created this admin
        created_at: Creation timestamp
    """

    __tablename__ = "admins"

    # Primary Key
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # Telegram Info
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Role & Permissions
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="admin"
    )

    # R10-3: Block status for compromised admins
    is_blocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    # Authentication
    master_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Creator tracking (self-referencing)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admins.id"), nullable=True
    )

    # Relationships

    # Self-referencing: creator admin
    creator: Mapped[Optional["Admin"]] = relationship(
        "Admin",
        remote_side="Admin.id",
        foreign_keys=[created_by],
        back_populates="created_admins",
    )

    # Self-referencing: admins created by this admin
    created_admins: Mapped[list["Admin"]] = relationship(
        "Admin",
        back_populates="creator",
        foreign_keys=[created_by],
    )

    # OneToMany: Sessions
    sessions: Mapped[list["AdminSession"]] = relationship(
        "AdminSession", back_populates="admin", lazy="selectin"
    )

    # OneToMany: Initiated wallet changes
    initiated_wallet_changes: Mapped[
        list["WalletChangeRequest"]
    ] = relationship(
        "WalletChangeRequest",
        foreign_keys="WalletChangeRequest.initiated_by_admin_id",
        back_populates="initiated_by",
        lazy="selectin",
    )

    # OneToMany: Approved wallet changes
    approved_wallet_changes: Mapped[
        list["WalletChangeRequest"]
    ] = relationship(
        "WalletChangeRequest",
        foreign_keys="WalletChangeRequest.approved_by_admin_id",
        back_populates="approved_by",
        lazy="selectin",
    )

    # Permission Properties

    @property
    def is_super_admin(self) -> bool:
        """Check if admin is super admin."""
        return self.role == "super_admin"

    @property
    def is_extended_admin(self) -> bool:
        """Check if admin is extended admin or higher."""
        return self.role in ("extended_admin", "super_admin")

    @property
    def is_admin(self) -> bool:
        """Check if admin has at least basic admin role."""
        return self.role in ("admin", "extended_admin", "super_admin")

    @property
    def can_stage_wallet_changes(self) -> bool:
        """Check if can initiate wallet change requests."""
        return self.is_extended_admin

    @property
    def can_approve_wallet_changes(self) -> bool:
        """Check if can approve wallet change requests."""
        return self.is_super_admin

    @property
    def display_name(self) -> str:
        """Get display name for admin."""
        return self.username or f"Admin{self.telegram_id}"

    @property
    def role_display(self) -> str | None:
        """Get formatted role name."""
        role_map = {
            "admin": "Admin",
            "extended_admin": "Extended Admin",
            "super_admin": "Super Admin",
        }
        return role_map.get(self.role, self.role)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Admin(id={self.id}, "
            f"telegram_id={self.telegram_id}, "
            f"role={self.role!r})"
        )
