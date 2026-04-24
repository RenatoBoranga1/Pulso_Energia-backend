from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import InsightType
from app.db.base_class import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.utility_bill import UtilityBill


class Insight(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "insights"

    bill_id: Mapped[UUID] = mapped_column(ForeignKey("utility_bills.id", ondelete="CASCADE"), nullable=False, index=True)
    insight_type: Mapped[InsightType] = mapped_column(
        Enum(InsightType, native_enum=False, validate_strings=True, length=32),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)

    bill: Mapped["UtilityBill"] = relationship(back_populates="insights")
