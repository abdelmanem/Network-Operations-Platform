from backend.app.transports.retry import TransportRetryPolicy


def test_retry_policy_uses_exponential_backoff() -> None:
    policy = TransportRetryPolicy(base_delay_seconds=0.5, max_delay_seconds=10.0)

    assert policy.delay_for_attempt(1) == 0.5
    assert policy.delay_for_attempt(3) == 2.0


def test_retry_policy_matches_retryable_status_code() -> None:
    policy = TransportRetryPolicy()

    assert policy.should_retry_status(503) is True
    assert policy.should_retry_status(418) is False
