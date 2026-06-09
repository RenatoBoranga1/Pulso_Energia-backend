from starlette.requests import Request

from app.api.dependencies.rate_limit import InMemoryRateLimiter, resolve_client_identifier


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


def test_resolve_client_identifier_prefers_forwarded_for() -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [
                (b"x-forwarded-for", b"203.0.113.10, 10.0.0.1"),
                (b"x-real-ip", b"198.51.100.20"),
            ],
            "client": ("10.0.0.2", 12345),
        },
    )

    assert resolve_client_identifier(request) == "203.0.113.10"
