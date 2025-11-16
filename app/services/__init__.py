"""
Services.

Business logic layer.
"""

# Core Services
from app.services.deposit_service import DepositService
from app.services.notification_service import NotificationService
from app.services.deposit_validation_service import DepositValidationService
from app.services.referral_service import ReferralService
from app.services.reward_service import RewardService
from app.services.transaction_service import TransactionService
from app.services.user_service import UserService
from app.services.withdrawal_service import WithdrawalService

# PART5 Critical Services
from app.services.notification_retry_service import (
    NotificationRetryService,
)
from app.services.payment_retry_service import PaymentRetryService

# Support & Admin Services
from app.services.admin_service import AdminService
from app.services.blacklist_service import BlacklistService
from app.services.support_service import SupportService

# Blockchain Service
from app.services.blockchain_service import (
    BlockchainService,
    get_blockchain_service,
    init_blockchain_service,
)

# Additional Services
# Temporarily disabled due to encoding issues
# from app.services.finpass_recovery_service import FinpassRecoveryService
# from app.services.settings_service import SettingsService  # Temporarily disabled due to encoding issues
from app.services.wallet_admin_service import WalletAdminService

__all__ = [
    # Core
    "DepositService",
    "NotificationService",
    "DepositValidationService",
    "ReferralService",
    "RewardService",
    "TransactionService",
    "UserService",
    "WithdrawalService",
    # PART5 Critical
    "NotificationRetryService",
    "PaymentRetryService",
    # Support & Admin
    "AdminService",
    "BlacklistService",
    "SupportService",
    # Blockchain
    "BlockchainService",
    "get_blockchain_service",
    "init_blockchain_service",
    # Additional
    # "FinpassRecoveryService",  # Temporarily disabled
    # "SettingsService",  # Temporarily disabled
    "WalletAdminService",
]
