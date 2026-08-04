from backend.app.integrations.netbox.retry import RetryPolicy


def test_retry_policy_uses_exponential_backoff() -> None:
    policy = RetryPolicy(base_delay_seconds=0.5, max_delay_seconds=5.0)

    assert policy.delay_for_attempt(1) == 0.5
    assert policy.delay_for_attempt(2) == 1.0
    assert policy.delay_for_attempt(4) == 4.0


def test_retry_policy_marks_retryable_status_codes() -> None:
    policy = RetryPolicy()

    assert policy.should_retry(429)
    assert policy.should_retry(503)
    assert not policy.should_retry(404)
