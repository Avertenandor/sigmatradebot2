"""
HTTP Health Check Server.

Provides /health endpoint for external monitoring (nginx, UptimeRobot, etc.).
"""

import asyncio
from typing import Any

from aiohttp import web
from loguru import logger

from app.utils.health_check import get_health_status_sync


async def health_handler(request: web.Request) -> web.Response:
    """
    Handle /health requests.

    Returns:
        JSON response with health status:
        - 200: All systems healthy
        - 503: One or more systems degraded/unhealthy
    """
    try:
        status = get_health_status_sync()
        overall_status = status.get("status", "unknown")

        # Determine HTTP status code
        if overall_status == "healthy":
            http_code = 200
        elif overall_status == "degraded":
            http_code = 503
        else:
            http_code = 503

        return web.json_response(status, status=http_code)

    except Exception as e:
        logger.error(f"Health check endpoint error: {e}")
        return web.json_response(
            {
                "status": "unhealthy",
                "error": str(e),
            },
            status=503,
        )


def create_health_app() -> web.Application:
    """
    Create aiohttp application for health checks.

    Returns:
        aiohttp Application instance
    """
    app = web.Application()
    app.router.add_get("/health", health_handler)
    return app


async def run_health_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """
    Run health check HTTP server.

    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port to bind to (default: 8080)
    """
    app = create_health_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info(f"Health check server running on {host}:{port}")


