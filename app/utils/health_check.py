"""
Health check utilities.

Provides health check functionality for the bot.
"""

import asyncio
from typing import Any

from loguru import logger
from sqlalchemy import text

from app.config.database import async_session_maker
from app.config.settings import settings
from app.services.blockchain_service import get_blockchain_service


async def check_database() -> dict[str, Any]:
    """
    Check database connectivity.

    Returns:
        Dict with status and details
    """
    try:
        async with async_session_maker() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()

        return {
            "status": "healthy",
            "message": "Database connection successful",
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
        }


async def check_redis() -> dict[str, Any]:
    """
    Check Redis connectivity.

    Returns:
        Dict with status and details
    """
    try:
        import redis.asyncio as redis

        redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            decode_responses=True,
        )

        await redis_client.ping()
        await redis_client.close()

        return {
            "status": "healthy",
            "message": "Redis connection successful",
        }
    except ImportError:
        return {
            "status": "unknown",
            "message": "Redis client not available",
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Redis connection failed: {str(e)}",
        }


async def check_blockchain() -> dict[str, Any]:
    """
    Check blockchain service connectivity.

    Returns:
        Dict with status and details
    """
    try:
        blockchain_service = get_blockchain_service()

        # Try to get chain ID (lightweight check)
        loop = asyncio.get_event_loop()
        chain_id = await loop.run_in_executor(
            None,
            lambda: blockchain_service.web3.eth.chain_id
        )

        # Get RPC stats
        rpc_stats = blockchain_service.get_rpc_stats()

        return {
            "status": "healthy",
            "message": (
                f"Blockchain connection successful (Chain ID: {chain_id})"
            ),
            "chain_id": chain_id,
            "rpc_stats": rpc_stats,
        }
    except RuntimeError as e:
        if "not initialized" in str(e):
            return {
                "status": "unhealthy",
                "message": "BlockchainService not initialized",
            }
        raise
    except Exception as e:
        logger.error(f"Blockchain health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Blockchain connection failed: {str(e)}",
        }


async def check_all() -> dict[str, Any]:
    """
    Perform all health checks.

    Returns:
        Dict with overall status and individual check results
    """
    results = {
        "database": await check_database(),
        "redis": await check_redis(),
        "blockchain": await check_blockchain(),
    }

    # Determine overall status
    all_healthy = all(
        check.get("status") == "healthy" for check in results.values()
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": results,
    }


def get_health_status_sync() -> dict[str, Any]:
    """
    Get health status synchronously (for use in HTTP endpoints).

    Returns:
        Dict with health status
    """
    try:
        # Run async health checks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(check_all())
        finally:
            loop.close()

        return result
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }
