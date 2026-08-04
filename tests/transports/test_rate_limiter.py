from backend.app.transports.rate_limiter import RateLimiter


def test_rate_limiter_try_acquire_consumes_tokens() -> None:
    limiter = RateLimiter(tokens_per_second=1.0, capacity=1.0)

    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False
