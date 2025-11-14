"""
Dramatiq worker entry point.

Starts the Dramatiq worker to process background tasks.
"""

import sys
from pathlib import Path

from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import broker to initialize
from jobs.broker import broker  # noqa: F401

# Import all tasks to register them with broker
from jobs.tasks import (  # noqa: F401
    daily_rewards,
    deposit_monitoring,
    notification_retry,
    payment_retry,
)

logger.info("Dramatiq worker initialized with all tasks")

# Worker is started via CLI: dramatiq jobs.worker
# Command: dramatiq jobs.worker -p 4 -t 4
# -p: number of processes
# -t: number of threads per process
