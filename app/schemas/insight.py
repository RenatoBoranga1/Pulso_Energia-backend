from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.core.enums import InsightType
from app.schemas.common import ORMModel


class InsightRead(ORMModel):
    id: UUID
    bill_id: UUID
    insight_type: InsightType
    message: str
    created_at: datetime

