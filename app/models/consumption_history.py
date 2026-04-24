from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.utility_bill import UtilityBill


class ConsumptionHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "consumption_history"
    __table_args__ = (
        UniqueConstraint("bill_id", "mes_referencia", name="consumption_history_bill_month_unique"),
        CheckConstraint("consumo_kwh >= 0", name="consumption_history_consumo_kwh_non_negative"),
        CheckConstraint("dias_faturados >= 0", name="consumption_history_dias_faturados_non_negative"),
    )

    bill_id: Mapped[UUID] = mapped_column(ForeignKey("utility_bills.id", ondelete="CASCADE"), nullable=False, index=True)
    mes_referencia: Mapped[str] = mapped_column(String(7), nullable=False)
    consumo_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    dias_faturados: Mapped[int | None] = mapped_column(nullable=True)

    bill: Mapped["UtilityBill"] = relationship(back_populates="consumption_history")
