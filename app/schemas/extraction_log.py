from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.core.enums import ExtractionLogLevel, ExtractionLogStage
from app.schemas.common import ORMModel


class ExtractionLogRead(ORMModel):
    id: UUID
    document_id: UUID
    bill_id: UUID | None = None
    stage: ExtractionLogStage
    level: ExtractionLogLevel
    message: str
    source_component: str | None = None
    created_at: datetime

