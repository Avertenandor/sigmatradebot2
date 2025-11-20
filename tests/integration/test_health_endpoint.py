"""
Integration tests for /health endpoint.

Tests that health endpoint returns correct status and RPC statistics.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.http_health_server import health_handler
from app.utils.health_check import check_blockchain


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint_includes_rpc_stats() -> None:
    """
    Test that health endpoint includes RPC statistics.

    Scenario:
    GIVEN: BlockchainService with RPC stats
    WHEN: Health endpoint is called
    THEN: Response includes rpc_stats with all required fields
    """
    # GIVEN: Mock blockchain service with RPC stats
    mock_rpc_stats = {
        "requests_last_minute": 42,
        "avg_response_time_ms": 115.5,
        "error_count": 0,
        "total_requests": 12345,
    }

    with patch(
        "app.utils.health_check.get_blockchain_service"
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_service.web3.eth.chain_id = 56
        mock_service.get_rpc_stats.return_value = mock_rpc_stats
        mock_get_service.return_value = mock_service

        # WHEN: Call health check
        result = await check_blockchain()

        # THEN: Should include RPC stats
        assert result["status"] == "healthy", "Should be healthy"
        assert "rpc_stats" in result, "Should include rpc_stats"
        assert (
            result["rpc_stats"]["requests_last_minute"] == 42
        ), "Should have correct requests_last_minute"
        assert (
            result["rpc_stats"]["avg_response_time_ms"] == 115.5
        ), "Should have correct avg_response_time_ms"
        assert (
            result["rpc_stats"]["error_count"] == 0
        ), "Should have correct error_count"
        assert (
            result["rpc_stats"]["total_requests"] == 12345
        ), "Should have correct total_requests"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint_200_when_all_healthy() -> None:
    """
    Test that health endpoint returns 200 when all components are healthy.

    Scenario:
    GIVEN: All components (database, redis, blockchain) are healthy
    WHEN: Health endpoint is called
    THEN: HTTP status code is 200
    """
    # GIVEN: Mock all health checks to return healthy
    with patch("app.utils.health_check.check_database") as mock_db, patch(
        "app.utils.health_check.check_redis"
    ) as mock_redis, patch(
        "app.utils.health_check.check_blockchain"
    ) as mock_blockchain:
        mock_db.return_value = {"status": "healthy", "message": "OK"}
        mock_redis.return_value = {"status": "healthy", "message": "OK"}
        mock_blockchain.return_value = {
            "status": "healthy",
            "message": "OK",
            "rpc_stats": {
                "requests_last_minute": 10,
                "avg_response_time_ms": 100,
                "error_count": 0,
                "total_requests": 1000,
            },
        }

        # WHEN: Call health handler
        request = MagicMock()
        response = await health_handler(request)

        # THEN: Should return 200
        assert response.status == 200, "Should return 200 when all healthy"

        # Parse JSON body
        import json

        body = json.loads(response.text)
        assert body["status"] == "healthy", "Overall status should be healthy"
        assert (
            body["checks"]["blockchain"]["status"] == "healthy"
        ), "Blockchain should be healthy"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint_503_when_blockchain_unhealthy() -> None:
    """
    Test that health endpoint returns 503 when blockchain is unhealthy.

    Scenario:
    GIVEN: Blockchain check returns unhealthy
    WHEN: Health endpoint is called
    THEN: HTTP status code is 503
    """
    # GIVEN: Mock blockchain check to return unhealthy
    with patch("app.utils.health_check.check_database") as mock_db, patch(
        "app.utils.health_check.check_redis"
    ) as mock_redis, patch(
        "app.utils.health_check.check_blockchain"
    ) as mock_blockchain:
        mock_db.return_value = {"status": "healthy", "message": "OK"}
        mock_redis.return_value = {"status": "healthy", "message": "OK"}
        mock_blockchain.return_value = {
            "status": "unhealthy",
            "message": "Blockchain connection failed",
        }

        # WHEN: Call health handler
        request = MagicMock()
        response = await health_handler(request)

        # THEN: Should return 503
        assert response.status == 503, "Should return 503 when blockchain unhealthy"

        # Parse JSON body
        import json

        body = json.loads(response.text)
        assert (
            body["status"] == "degraded"
        ), "Overall status should be degraded"
        assert (
            body["checks"]["blockchain"]["status"] == "unhealthy"
        ), "Blockchain should be unhealthy"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint_rpc_stats_structure() -> None:
    """
    Test that RPC stats have correct structure.

    Scenario:
    GIVEN: BlockchainService returns RPC stats
    WHEN: Health endpoint is called
    THEN: RPC stats have all required fields with correct types
    """
    # GIVEN: Mock blockchain service
    mock_rpc_stats = {
        "requests_last_minute": 25,
        "avg_response_time_ms": 150.0,
        "error_count": 2,
        "total_requests": 5000,
    }

    with patch(
        "app.utils.health_check.get_blockchain_service"
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_service.web3.eth.chain_id = 56
        mock_service.get_rpc_stats.return_value = mock_rpc_stats
        mock_get_service.return_value = mock_service

        # WHEN: Call health check
        result = await check_blockchain()

        # THEN: RPC stats should have correct structure
        assert "rpc_stats" in result, "Should have rpc_stats"
        rpc_stats = result["rpc_stats"]

        # Check all required fields exist
        assert "requests_last_minute" in rpc_stats
        assert "avg_response_time_ms" in rpc_stats
        assert "error_count" in rpc_stats
        assert "total_requests" in rpc_stats

        # Check types
        assert isinstance(rpc_stats["requests_last_minute"], int)
        assert isinstance(rpc_stats["avg_response_time_ms"], (int, float))
        assert isinstance(rpc_stats["error_count"], int)
        assert isinstance(rpc_stats["total_requests"], int)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint_handles_missing_blockchain_service() -> None:
    """
    Test that health endpoint handles missing BlockchainService gracefully.

    Scenario:
    GIVEN: BlockchainService is not initialized
    WHEN: Health endpoint is called
    THEN: Returns unhealthy status with appropriate message
    """
    # GIVEN: BlockchainService not initialized
    with patch(
        "app.utils.health_check.get_blockchain_service"
    ) as mock_get_service:
        mock_get_service.side_effect = RuntimeError(
            "BlockchainService not initialized"
        )

        # WHEN: Call health check
        result = await check_blockchain()

        # THEN: Should return unhealthy
        assert result["status"] == "unhealthy", "Should be unhealthy"
        assert (
            "not initialized" in result["message"].lower()
        ), "Should mention not initialized"

