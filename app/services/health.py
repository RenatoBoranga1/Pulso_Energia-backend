from __future__ import annotations

from datetime import datetime, timezone

from fastapi import status
from sqlalchemy import text

from app.core.config import Settings
from app.db.session import get_engine
from app.schemas.health import HealthDependency, HealthResponse


class HealthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def check(self) -> tuple[int, HealthResponse]:
        dependencies: dict[str, HealthDependency] = {}
        http_status = status.HTTP_200_OK
        overall_status = "healthy"

        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
            dependencies["database"] = HealthDependency(
                status="healthy",
                details="Database connection is available.",
            )
        except Exception as exc:
            overall_status = "degraded"
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            dependencies["database"] = HealthDependency(
                status="unhealthy",
                details=f"Database connectivity check failed: {exc.__class__.__name__}.",
            )

        payload = HealthResponse(
            status=overall_status,
            service=self.settings.app_name,
            version=self.settings.app_version,
            environment=self.settings.environment,
            timestamp=datetime.now(timezone.utc),
            dependencies=dependencies,
        )
        return http_status, payload

