"""
Repositories.

Data access layer for all models.
"""

# Admin Repositories
from app.repositories.admin_repository import AdminRepository
from app.repositories.admin_session_repository import (
    AdminSessionRepository,
)
from app.repositories.appeal_repository import AppealRepository
from app.repositories.base import BaseRepository

# Security Repositories
from app.repositories.blacklist_repository import (
    BlacklistRepository,
)
from app.repositories.deposit_repository import DepositRepository
from app.repositories.deposit_reward_repository import (
    DepositRewardRepository,
)
from app.repositories.deposit_level_version_repository import (
    DepositLevelVersionRepository,
)
from app.repositories.failed_notification_repository import (
    FailedNotificationRepository,
)
from app.repositories.financial_password_recovery_repository import (
    FinancialPasswordRecoveryRepository,
)

# PART5 Critical Repositories
from app.repositories.payment_retry_repository import (
    PaymentRetryRepository,
)
from app.repositories.referral_earning_repository import (
    ReferralEarningRepository,
)
from app.repositories.referral_repository import ReferralRepository

# Reward Repositories
from app.repositories.reward_session_repository import (
    RewardSessionRepository,
)
from app.repositories.support_message_repository import (
    SupportMessageRepository,
)

# Support Repositories
from app.repositories.support_ticket_repository import (
    SupportTicketRepository,
)

# System Repositories
from app.repositories.global_settings_repository import (
    GlobalSettingsRepository,
)
from app.repositories.transaction_repository import (
    TransactionRepository,
)
from app.repositories.user_action_repository import (
    UserActionRepository,
)

# Core Repositories
from app.repositories.user_repository import UserRepository
from app.repositories.user_notification_settings_repository import (
    UserNotificationSettingsRepository,
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
    "DepositLevelVersionRepository",
    "TransactionRepository",
    "ReferralRepository",
    "UserNotificationSettingsRepository",
    # Admin
    "AdminRepository",
    "AdminSessionRepository",
    # Security
    "BlacklistRepository",
    "FinancialPasswordRecoveryRepository",
    "AppealRepository",
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
    "GlobalSettingsRepository",
    "UserActionRepository",
    "WalletChangeRequestRepository",
]
