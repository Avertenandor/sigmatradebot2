"""
Background tasks.

Dramatiq task definitions.
"""

from jobs.tasks.daily_rewards import process_daily_rewards
from jobs.tasks.deposit_monitoring import monitor_deposits
from jobs.tasks.financial_reconciliation import (
    perform_financial_reconciliation,
)
from jobs.tasks.notification_retry import process_notification_retries
from jobs.tasks.payment_retry import process_payment_retries
from jobs.tasks.metrics_monitor import monitor_metrics
from jobs.tasks.node_health_monitor import monitor_node_health
from jobs.tasks.stuck_transaction_monitor import monitor_stuck_transactions
from jobs.tasks.notification_fallback import process_notification_fallback
from jobs.tasks.warmup_redis_cache import warmup_redis_cache
from jobs.tasks.admin_session_cleanup import cleanup_expired_admin_sessions
from jobs.tasks.mark_immutable_audit_logs import mark_immutable_audit_logs
from jobs.tasks.redis_recovery import recover_redis_data
from jobs.tasks.notification_fallback_processor import (
    process_notification_fallback as process_notification_fallback_v2,
)

__all__ = [
    "process_daily_rewards",
    "monitor_deposits",
    "process_notification_retries",
    "process_payment_retries",
    "monitor_stuck_transactions",
    "monitor_node_health",
    "monitor_metrics",
    "perform_financial_reconciliation",
    "process_notification_fallback",
    "warmup_redis_cache",
    "cleanup_expired_admin_sessions",
    "mark_immutable_audit_logs",
    "recover_redis_data",
    "process_notification_fallback_v2",
]
