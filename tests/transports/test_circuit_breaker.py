from datetime import UTC, datetime, timedelta

from backend.app.transports.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
)


def test_circuit_breaker_opens_after_threshold() -> None:
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=1.0)

    assert breaker.allow_request() is True
    breaker.record_failure()
    breaker.record_failure()

    assert breaker.state == CircuitBreakerState.OPEN
    assert breaker.allow_request() is False


def test_circuit_breaker_transitions_to_half_open_after_timeout() -> None:
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=1.0)
    breaker.record_failure()
    breaker.opened_at = datetime.now(UTC) - timedelta(seconds=2)

    assert breaker.allow_request() is True
    assert breaker.state == CircuitBreakerState.HALF_OPEN
