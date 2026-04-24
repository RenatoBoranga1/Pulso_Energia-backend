from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from functools import lru_cache
from threading import Lock
from time import monotonic

from fastapi import Depends, Request, status

from app.core.config import Settings, get_settings
from app.core.errors import AppError


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def enforce(self, *, key: str, limit: int, window_seconds: int) -> int | None:
        now = monotonic()
        window_start = now - window_seconds

        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= window_start:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, int(bucket[0] + window_seconds - now))
                return retry_after

            bucket.append(now)
            return None


@lru_cache
def get_rate_limiter() -> InMemoryRateLimiter:
    return InMemoryRateLimiter()


def build_rate_limit_dependency(
    *,
    scope: str,
    limit_setting: str,
    window_setting: str,
) -> Callable[..., None]:
    def dependency(
        request: Request,
        settings: Settings = Depends(get_settings),
    ) -> None:
        if not settings.rate_limit_enabled:
            return

        limit = int(getattr(settings, limit_setting))
        window_seconds = int(getattr(settings, window_setting))
        if limit <= 0 or window_seconds <= 0:
            return

        client_host = request.client.host if request.client is not None and request.client.host else "unknown"
        key = f"{scope}:{client_host}"
        retry_after_seconds = get_rate_limiter().enforce(
            key=key,
            limit=limit,
            window_seconds=window_seconds,
        )
        if retry_after_seconds is None:
            return

        raise AppError(
            "Rate limit exceeded for this operation.",
            code="rate_limit_exceeded",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={
                "scope": scope,
                "limit": limit,
                "window_seconds": window_seconds,
                "retry_after_seconds": retry_after_seconds,
            },
            headers={"Retry-After": str(retry_after_seconds)},
        )

    return dependency


auth_rate_limit = build_rate_limit_dependency(
    scope="auth",
    limit_setting="auth_rate_limit_requests",
    window_setting="auth_rate_limit_window_seconds",
)

upload_rate_limit = build_rate_limit_dependency(
    scope="upload",
    limit_setting="upload_rate_limit_requests",
    window_setting="upload_rate_limit_window_seconds",
)

extraction_rate_limit = build_rate_limit_dependency(
    scope="extract",
    limit_setting="extraction_rate_limit_requests",
    window_setting="extraction_rate_limit_window_seconds",
)
