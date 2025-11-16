"""
Database enums.

Centralized enums used across database models.
"""

from enum import StrEnum


class TransactionStatus(StrEnum):
    """Transaction status values."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class TransactionType(StrEnum):
    """Transaction type values."""

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    REFERRAL_REWARD = "referral_reward"
    DEPOSIT_REWARD = "deposit_reward"
    SYSTEM_PAYOUT = "system_payout"


class WalletChangeType(StrEnum):
    """Wallet change request type values."""

    SYSTEM_DEPOSIT = "system_deposit"
    PAYOUT_WITHDRAWAL = "payout_withdrawal"


class WalletChangeStatus(StrEnum):
    """Wallet change request status values."""

    PENDING = "pending"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"


class SupportTicketStatus(StrEnum):
    """Support ticket status values."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_USER = "waiting_user"
    ANSWERED = "answered"  # Alias for when admin responds
    RESOLVED = "resolved"
    CLOSED = "closed"


# Alias for backward compatibility
SupportStatus = SupportTicketStatus


class SupportTicketPriority(StrEnum):
    """Support ticket priority values."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SupportCategory(StrEnum):
    """Support ticket category values."""

    PAYMENTS = "payments"
    WITHDRAWALS = "withdrawals"
    FINPASS = "finpass"
    REFERRALS = "referrals"
    TECH = "tech"
    OTHER = "other"


class SupportSender(StrEnum):
    """Support message sender values."""

    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"
