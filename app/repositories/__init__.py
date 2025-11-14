"""
Repositories.

Data access layer for all models.
"""

from app.repositories.base import BaseRepository

# Core Repositories
from app.repositories.user_repository import UserRepository
from app.repositories.deposit_repository import DepositRepository
from app.repositories.transaction_repository import (
    TransactionRepository,
)
from app.repositories.referral_repository import ReferralRepository

# Admin Repositories
from app.repositories.admin_repository import AdminRepository
from app.repositories.admin_session_repository import (
    AdminSessionRepository,
)

# Security Repositories
from app.repositories.blacklist_repository import (
    BlacklistRepository,
)
from app.repositories.financial_password_recovery_repository import (
    FinancialPasswordRecoveryRepository,
)

# Reward Repositories
from app.repositories.reward_session_repository import (
    RewardSessionRepository,
)
from app.repositories.deposit_reward_repository import (
    DepositRewardRepository,
)
from app.repositories.referral_earning_repository import (
    ReferralEarningRepository,
)

# PART5 Critical Repositories
from app.repositories.payment_retry_repository import (
    PaymentRetryRepository,
)
from app.repositories.failed_notification_repository import (
    FailedNotificationRepository,
)

# Support Repositories
from app.repositories.support_ticket_repository import (
    SupportTicketRepository,
)
from app.repositories.support_message_repository import (
    SupportMessageRepository,
)

# System Repositories
from app.repositories.system_setting_repository import (
    SystemSettingRepository,
)
from app.repositories.user_action_repository import (
    UserActionRepository,
)
from app.repositories.wallet_change_request_repository import (
    WalletChangeRequestRepository,
)

__all__ = [
    # Base
    "BaseRepository",
    # Core
    "UserRepository",
    "DepositRepository",
    "TransactionRepository",
    "ReferralRepository",
    # Admin
    "AdminRepository",
    "AdminSessionRepository",
    # Security
    "BlacklistRepository",
    "FinancialPasswordRecoveryRepository",
    # Rewards
    "RewardSessionRepository",
    "DepositRewardRepository",
    "ReferralEarningRepository",
    # PART5 Critical
    "PaymentRetryRepository",
    "FailedNotificationRepository",
    # Support
    "SupportTicketRepository",
    "SupportMessageRepository",
    # System
    "SystemSettingRepository",
    "UserActionRepository",
    "WalletChangeRequestRepository",
]
