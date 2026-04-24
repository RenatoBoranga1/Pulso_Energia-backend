from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ExtractionLogLevel, ExtractionLogStage
from app.models.extraction_log import ExtractionLog


class ExtractionLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        *,
        document_id: UUID,
        bill_id: UUID | None,
        stage: ExtractionLogStage,
        level: ExtractionLogLevel,
        message: str,
        source_component: str | None = None,
    ) -> ExtractionLog:
        log = ExtractionLog(
            document_id=document_id,
            bill_id=bill_id,
            stage=stage,
            level=level,
            message=message,
            source_component=source_component,
        )
        self.session.add(log)
        self.session.flush()
        return log

    def list_for_bill(self, bill_id: UUID) -> list[ExtractionLog]:
        statement = (
            select(ExtractionLog)
            .where(ExtractionLog.bill_id == bill_id)
            .order_by(ExtractionLog.created_at.asc(), ExtractionLog.id.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    def list_for_document(self, document_id: UUID) -> list[ExtractionLog]:
        statement = (
            select(ExtractionLog)
            .where(ExtractionLog.document_id == document_id)
            .order_by(ExtractionLog.created_at.asc(), ExtractionLog.id.asc())
        )
        return list(self.session.execute(statement).scalars().all())

