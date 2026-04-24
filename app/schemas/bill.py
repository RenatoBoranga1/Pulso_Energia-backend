from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints

from app.core.enums import BillExtractionStatus
from app.schemas.common import ORMModel
from app.schemas.document import UploadedDocumentRead


ReferenceMonth = Annotated[
    str,
    StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", min_length=7, max_length=7),
]


class ConsumptionHistoryRead(ORMModel):
    id: UUID
    bill_id: UUID
    mes_referencia: ReferenceMonth
    consumo_kwh: Decimal
    dias_faturados: int | None = None


class ExtractionConfidenceRead(ORMModel):
    id: UUID
    bill_id: UUID
    field_name: str
    confidence_score: Annotated[Decimal, Field(ge=0, le=1)]


class UtilityBillRead(ORMModel):
    id: UUID
    user_id: UUID
    document_id: UUID
    concessionaria: str | None = None
    mes_referencia: ReferenceMonth | None = None
    consumo_kwh: Decimal | None = None
    dias_faturados: int | None = None
    valor_total: Decimal | None = None
    bandeira_tarifaria: str | None = None
    unidade_consumidora: str | None = None
    vencimento: date | None = None
    extraction_status: BillExtractionStatus
    review_required: bool
    created_at: datetime


class UtilityBillDetailRead(UtilityBillRead):
    document: UploadedDocumentRead | None = None
    consumption_history: list[ConsumptionHistoryRead] = Field(default_factory=list)
    confidence_scores: list[ExtractionConfidenceRead] = Field(default_factory=list)
