"""
Dramatiq broker configuration.

Redis-based message broker for task queue.
"""

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from loguru import logger

from app.config.settings import settings

# Initialize Redis broker
redis_broker = RedisBroker(
    host=settings.redis_host,
    port=settings.redis_port,
    password=settings.redis_password if settings.redis_password else None,
    db=settings.redis_db,
)

# Set as default broker
dramatiq.set_broker(redis_broker)

# Export broker
broker = redis_broker

logger.info(
    f"Dramatiq broker initialized: "
    f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
)
