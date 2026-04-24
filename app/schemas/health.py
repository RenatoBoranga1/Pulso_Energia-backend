from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthDependency(BaseModel):
    status: Literal["healthy", "unhealthy"]
    details: str


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    service: str
    version: str
    environment: str
    timestamp: datetime
    dependencies: dict[str, HealthDependency]

