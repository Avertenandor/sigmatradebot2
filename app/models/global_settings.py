"""
Global Settings model.

Stores global dynamic settings configurable via Admin Panel.
Singleton pattern (only one row expected).
"""

from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base


class GlobalSettings(Base):
    """Global settings model."""

    __tablename__ = "global_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Withdrawal settings
    min_withdrawal_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0.05"), nullable=False
    )
    daily_withdrawal_limit: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    is_daily_limit_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    auto_withdrawal_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<GlobalSettings(min_withdrawal={self.min_withdrawal_amount}, "
            f"daily_limit={self.daily_withdrawal_limit}, "
            f"auto_enabled={self.auto_withdrawal_enabled})>"
        )

