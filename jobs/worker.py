"""
Dramatiq worker entry point.

Starts the Dramatiq worker to process background tasks.
"""

import sys
import warnings
from pathlib import Path

# Suppress eth_utils network warnings about invalid ChainId
# These warnings are from eth_utils library initialization and don't affect functionality
# Must be set BEFORE importing any modules that use eth_utils
warnings.filterwarnings(
    "ignore",
    message=".*does not have a valid ChainId.*",
    category=UserWarning,
    module="eth_utils.network",
)
# Also suppress warnings from any module that may import eth_utils
warnings.filterwarnings(
    "ignore",
    message=".*does not have a valid ChainId.*",
    category=UserWarning,
)

from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Initialize settings and blockchain service
from app.config.database import async_session_maker
from app.config.settings import settings
from app.services.blockchain_service import init_blockchain_service

# Initialize BlockchainService for worker tasks
try:
    init_blockchain_service(
        settings=settings,
        session_factory=async_session_maker,
    )
    logger.info("BlockchainService initialized for worker")
except Exception as e:
    logger.error(f"Failed to initialize BlockchainService: {e}")
    logger.warning("Worker will continue, but blockchain operations may fail")

# Import broker to initialize
from jobs.broker import broker  # noqa: F401

# Import all tasks to register them with broker
from jobs.tasks import (  # noqa: F401
    daily_rewards,
    deposit_monitoring,
    notification_retry,
    payment_retry,
    incoming_transfer_monitor,
)

logger.info("Dramatiq worker initialized with all tasks")

# Worker is started via CLI: dramatiq jobs.worker
# Command: dramatiq jobs.worker -p 4 -t 4
# -p: number of processes
# -t: number of threads per process
