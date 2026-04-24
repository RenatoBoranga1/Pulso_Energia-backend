from app.api.dependencies.rate_limit import InMemoryRateLimiter


def test_rate_limiter_blocks_after_limit() -> None:
    limiter = InMemoryRateLimiter()

    assert limiter.enforce(key="auth:127.0.0.1", limit=2, window_seconds=60) is None
    assert limiter.enforce(key="auth:127.0.0.1", limit=2, window_seconds=60) is None

    retry_after = limiter.enforce(key="auth:127.0.0.1", limit=2, window_seconds=60)

    assert retry_after is not None
    assert retry_after >= 1


def test_rate_limiter_keeps_scopes_isolated() -> None:
    limiter = InMemoryRateLimiter()

    assert limiter.enforce(key="auth:127.0.0.1", limit=1, window_seconds=60) is None
    assert limiter.enforce(key="upload:127.0.0.1", limit=1, window_seconds=60) is None
