"""
Circuit Breaker for Database Operations.

R11-1: Implements circuit breaker pattern for gradual recovery after database failures.
"""

from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from loguru import logger


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker for database operations.

    R11-1: Implements gradual recovery phases:
    - Phase 1 (0-5 min): Read-only mode
    - Phase 2 (5-15 min): User operations allowed
    - Phase 3 (15+ min): Full operations

    Prevents overwhelming the database during recovery.
    """

    # Phase durations (in seconds)
    PHASE_1_DURATION = 300  # 5 minutes - read-only
    PHASE_2_DURATION = 600  # 10 minutes - user operations
    PHASE_3_DURATION = 900  # 15 minutes - full operations

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 3,
    ) -> None:
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before trying half-open
            success_threshold: Number of successes to close circuit
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None
        self.recovery_start_time: datetime | None = None

    def record_success(self) -> None:
        """Record successful operation."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info("R11-1: Circuit breaker closed - database recovered")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.recovery_start_time = None
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(UTC)

        if self.failure_count >= self.failure_threshold:
            if self.state == CircuitState.CLOSED:
                logger.warning(
                    f"R11-1: Circuit breaker opened - "
                    f"{self.failure_count} failures detected"
                )
                self.state = CircuitState.OPEN
                self.recovery_start_time = datetime.now(UTC)
            elif self.state == CircuitState.HALF_OPEN:
                # Failed during recovery, go back to open
                logger.warning(
                    "R11-1: Circuit breaker reopened - recovery failed"
                )
                self.state = CircuitState.OPEN
                self.success_count = 0
                self.recovery_start_time = datetime.now(UTC)

    def can_proceed(self, operation_type: str = "read") -> tuple[bool, str | None]:
        """
        Check if operation can proceed.

        R11-1: Implements phase-based recovery.

        Args:
            operation_type: Type of operation ("read", "write", "admin")

        Returns:
            Tuple of (can_proceed, reason_if_not)
        """
        now = datetime.now(UTC)

        # Check if we should transition to half-open
        if self.state == CircuitState.OPEN:
            if self.recovery_start_time:
                elapsed = (now - self.recovery_start_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    logger.info("R11-1: Circuit breaker half-open - testing recovery")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    return False, "Circuit breaker is open - database unavailable"

        # Phase-based recovery
        if self.state == CircuitState.HALF_OPEN or (
            self.state == CircuitState.CLOSED and self.recovery_start_time
        ):
            if self.recovery_start_time:
                elapsed = (now - self.recovery_start_time).total_seconds()

                # Phase 1: Read-only (0-5 min)
                if elapsed < self.PHASE_1_DURATION:
                    if operation_type != "read":
                        return (
                            False,
                            "Phase 1 recovery: Read-only mode. "
                            "Write operations temporarily disabled.",
                        )

                # Phase 2: User operations (5-15 min)
                elif elapsed < self.PHASE_1_DURATION + self.PHASE_2_DURATION:
                    if operation_type == "admin":
                        return (
                            False,
                            "Phase 2 recovery: Admin operations temporarily disabled.",
                        )

                # Phase 3: Full operations (15+ min)
                # All operations allowed

        return True, None

    def get_recovery_phase(self) -> int | None:
        """
        Get current recovery phase.

        Returns:
            Phase number (1, 2, 3) or None if not in recovery
        """
        if not self.recovery_start_time:
            return None

        now = datetime.now(UTC)
        elapsed = (now - self.recovery_start_time).total_seconds()

        if elapsed < self.PHASE_1_DURATION:
            return 1
        elif elapsed < self.PHASE_1_DURATION + self.PHASE_2_DURATION:
            return 2
        elif elapsed < (
            self.PHASE_1_DURATION + self.PHASE_2_DURATION + self.PHASE_3_DURATION
        ):
            return 3
        else:
            # Recovery complete
            self.recovery_start_time = None
            return None

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        logger.info("R11-1: Circuit breaker reset to closed state")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.recovery_start_time = None


# Global circuit breaker instance
_db_circuit_breaker: CircuitBreaker | None = None


def get_db_circuit_breaker() -> CircuitBreaker:
    """
    Get global database circuit breaker instance.

    Returns:
        CircuitBreaker instance
    """
    global _db_circuit_breaker
    if _db_circuit_breaker is None:
        _db_circuit_breaker = CircuitBreaker()
    return _db_circuit_breaker


def reset_db_circuit_breaker() -> None:
    """Reset global database circuit breaker."""
    global _db_circuit_breaker
    if _db_circuit_breaker:
        _db_circuit_breaker.reset()

