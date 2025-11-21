"""
User FSM State model.

R11-2: Fallback storage for FSM states in PostgreSQL when Redis is unavailable.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserFsmState(Base):
    """
    User FSM state storage.

    R11-2: Stores FSM states in PostgreSQL as fallback when Redis is unavailable.
    """

    __tablename__ = "user_fsm_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    state: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="fsm_states")

