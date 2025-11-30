"""
Global Settings model.

Stores global dynamic settings configurable via Admin Panel.
Singleton pattern (only one row expected).
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


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
    withdrawal_service_fee: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), nullable=False
    )
    
    # Blockchain settings
    active_rpc_provider: Mapped[str] = mapped_column(
        String(20), default="quicknode", nullable=False
    )  # quicknode, nodereal
    is_auto_switch_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # Deposit settings
    max_open_deposit_level: Mapped[int] = mapped_column(
        Integer, default=5, nullable=False
    )
    
    # ROI Corridor settings (JSON)
    # Structure: {
    #   "level_1": {"mode": "custom", "min": "0.8", "max": "1.2", "fixed": "1.0"},
    #   "level_1_next": {...},
    #   ...
    #   "accrual_period_hours": 6
    # }
    roi_settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )

    # Emergency stop flags (R17-3)
    emergency_stop_withdrawals: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    emergency_stop_deposits: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    emergency_stop_roi: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<GlobalSettings(min_withdrawal={self.min_withdrawal_amount}, "
            f"daily_limit={self.daily_withdrawal_limit}, "
            f"auto_enabled={self.auto_withdrawal_enabled}, "
            f"active_rpc={self.active_rpc_provider}, "
            f"max_level={self.max_open_deposit_level})>"
        )
