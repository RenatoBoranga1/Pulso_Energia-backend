from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.utility_bill import UtilityBill


class ExtractionConfidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "extraction_confidence"
    __table_args__ = (
        UniqueConstraint("bill_id", "field_name", name="extraction_confidence_bill_field_unique"),
        CheckConstraint("confidence_score >= 0", name="extraction_confidence_score_min"),
        CheckConstraint("confidence_score <= 1", name="extraction_confidence_score_max"),
    )

    bill_id: Mapped[UUID] = mapped_column(ForeignKey("utility_bills.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)

    bill: Mapped["UtilityBill"] = relationship(back_populates="confidence_scores")
