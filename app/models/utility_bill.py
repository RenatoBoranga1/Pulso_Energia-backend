from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import BillExtractionStatus
from app.db.base_class import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.consumption_history import ConsumptionHistory
    from app.models.extraction_confidence import ExtractionConfidence
    from app.models.extraction_log import ExtractionLog
    from app.models.forecast import Forecast
    from app.models.insight import Insight
    from app.models.uploaded_document import UploadedDocument
    from app.models.user import User


class UtilityBill(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "utility_bills"
    __table_args__ = (
        CheckConstraint("consumo_kwh >= 0", name="utility_bills_consumo_kwh_non_negative"),
        CheckConstraint("dias_faturados >= 0", name="utility_bills_dias_faturados_non_negative"),
        CheckConstraint("valor_total >= 0", name="utility_bills_valor_total_non_negative"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("uploaded_documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    concessionaria: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mes_referencia: Mapped[str | None] = mapped_column(String(7), nullable=True, index=True)
    consumo_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    dias_faturados: Mapped[int | None] = mapped_column(nullable=True)
    valor_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    bandeira_tarifaria: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unidade_consumidora: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vencimento: Mapped[date | None] = mapped_column(nullable=True)
    extraction_status: Mapped[BillExtractionStatus] = mapped_column(
        Enum(BillExtractionStatus, native_enum=False, validate_strings=True, length=32),
        nullable=False,
        default=BillExtractionStatus.PENDING_REVIEW,
    )
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped["User"] = relationship(back_populates="utility_bills")
    document: Mapped["UploadedDocument"] = relationship(back_populates="utility_bill")
    consumption_history: Mapped[list["ConsumptionHistory"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
    )
    confidence_scores: Mapped[list["ExtractionConfidence"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
    )
    forecasts: Mapped[list["Forecast"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
    )
    insights: Mapped[list["Insight"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
    )
    extraction_logs: Mapped[list["ExtractionLog"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
    )
