"""
User wallet history model.

Tracks history of user wallet changes.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UserWalletHistory(Base):
    """User wallet history model."""

    __tablename__ = "user_wallet_history"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    old_wallet_address: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    new_wallet_address: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    
    # Relationship
    user: Mapped["User"] = relationship("User", backref="wallet_history")

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<UserWalletHistory(user_id={self.user_id}, "
            f"old={self.old_wallet_address}, new={self.new_wallet_address})>"
        )

