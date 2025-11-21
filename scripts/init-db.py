#!/usr/bin/env python3
"""Initialize database tables."""

import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import settings  # noqa: E402
from app.models.admin import Admin  # noqa: E402, F401
from app.models.admin_session import AdminSession  # noqa: E402, F401
from app.models.appeal import Appeal  # noqa: E402, F401
from app.models.base import Base  # noqa: E402
from app.models.blacklist import Blacklist  # noqa: E402, F401
from app.models.deposit import Deposit  # noqa: E402, F401
from app.models.deposit_reward import DepositReward  # noqa: E402, F401
from app.models.failed_notification import FailedNotification  # noqa: E402, F401
from app.models.financial_password_recovery import (  # noqa: E402, F401
    FinancialPasswordRecovery,
)
from app.models.payment_retry import PaymentRetry  # noqa: E402, F401
from app.models.referral import Referral  # noqa: E402, F401
from app.models.referral_earning import ReferralEarning  # noqa: E402, F401
from app.models.reward_session import RewardSession  # noqa: E402, F401
from app.models.support_message import SupportMessage  # noqa: E402, F401
from app.models.support_ticket import SupportTicket  # noqa: E402, F401
from app.models.system_setting import SystemSetting  # noqa: E402, F401
from app.models.transaction import Transaction  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
from app.models.user_action import UserAction  # noqa: E402, F401
from app.models.user_fsm_state import UserFsmState  # noqa: E402, F401
from app.models.wallet_change_request import (  # noqa: E402, F401
    WalletChangeRequest,
)


async def init_db():
    """Create all database tables."""
    print("Creating database tables...")
    
    engine = create_async_engine(settings.database_url, echo=True)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()
    
    print("✅ Database tables created successfully!")


if __name__ == "__main__":
    asyncio.run(init_db())
