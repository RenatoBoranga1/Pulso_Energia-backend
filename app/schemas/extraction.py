from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.core.enums import BillExtractionStatus
from app.schemas.bill import ReferenceMonth, UtilityBillDetailRead
from app.schemas.document import UploadedDocumentRead
from app.schemas.extraction_log import ExtractionLogRead


class HistoricalConsumptionEntry(BaseModel):
    mes_referencia: ReferenceMonth
    consumo_kwh: Annotated[Decimal, Field(gt=0)]
    dias_faturados: Annotated[int | None, Field(default=None, ge=0, le=60)]


class ReviewedBillData(BaseModel):
    concessionaria: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=255)] = None
    mes_referencia: ReferenceMonth | None = None
    consumo_kwh: Annotated[Decimal | None, Field(default=None, gt=0)] = None
    dias_faturados: Annotated[int | None, Field(default=None, ge=0, le=60)] = None
    valor_total: Annotated[Decimal | None, Field(default=None, gt=0)] = None
    bandeira_tarifaria: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=100)] = None
    unidade_consumidora: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=100)] = None
    vencimento: date | None = None
    historico_consumo: list[HistoricalConsumptionEntry] = Field(default_factory=list)


class ExtractedBillData(ReviewedBillData):
    confidence: dict[str, Annotated[float, Field(ge=0.0, le=1.0)]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ExtractBillRequest(BaseModel):
    document_id: UUID


class ConfirmBillRequest(BaseModel):
    data: ReviewedBillData


class BillReviewResponse(BaseModel):
    bill_id: UUID
    document: UploadedDocumentRead
    extraction_status: BillExtractionStatus
    review_required: bool
    structured_data: ExtractedBillData
    fields_for_review: list[str]
    bill: UtilityBillDetailRead
    logs: list[ExtractionLogRead]


class UserBillHistoryEntry(BaseModel):
    bill_id: UUID
    document_id: UUID
    mes_referencia: str | None
    concessionaria: str | None
    consumo_kwh: Decimal | None
    valor_total: Decimal | None
    extraction_status: BillExtractionStatus
    review_required: bool


class UserBillHistoryResponse(BaseModel):
    user_id: UUID
    bills: list[UserBillHistoryEntry]
