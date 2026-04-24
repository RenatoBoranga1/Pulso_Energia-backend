from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.utility_bill import UtilityBill


class Forecast(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint("bill_id", "mes_referencia", name="forecasts_bill_month_unique"),
        CheckConstraint("predicted_kwh >= 0", name="forecasts_predicted_kwh_non_negative"),
        CheckConstraint("lower_bound_kwh >= 0", name="forecasts_lower_bound_non_negative"),
        CheckConstraint("upper_bound_kwh >= 0", name="forecasts_upper_bound_non_negative"),
        CheckConstraint("lower_bound_kwh <= upper_bound_kwh", name="forecasts_bounds_ordered"),
    )

    bill_id: Mapped[UUID] = mapped_column(ForeignKey("utility_bills.id", ondelete="CASCADE"), nullable=False, index=True)
    mes_referencia: Mapped[str] = mapped_column(String(7), nullable=False)
    predicted_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    lower_bound_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    upper_bound_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)

    bill: Mapped["UtilityBill"] = relationship(back_populates="forecasts")
