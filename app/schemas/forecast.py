from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.schemas.bill import ReferenceMonth
from app.schemas.common import ORMModel


class ForecastRead(ORMModel):
    id: UUID
    bill_id: UUID
    mes_referencia: ReferenceMonth
    predicted_kwh: Decimal
    lower_bound_kwh: Decimal
    upper_bound_kwh: Decimal
    estimated_value_brl: Decimal | None = None
    lower_bound_value_brl: Decimal | None = None
    upper_bound_value_brl: Decimal | None = None
    model_used: str
    created_at: datetime
