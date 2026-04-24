from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.forecast import Forecast


class ForecastRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_bill_id(self, bill_id: UUID) -> list[Forecast]:
        statement = (
            select(Forecast)
            .where(Forecast.bill_id == bill_id)
            .order_by(Forecast.mes_referencia.asc(), Forecast.created_at.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    def replace_for_bill(self, *, bill_id: UUID, forecasts: list[Forecast]) -> list[Forecast]:
        self.delete_for_bill(bill_id)
        for forecast in forecasts:
            forecast.bill_id = bill_id
            self.session.add(forecast)
        self.session.flush()
        return forecasts

    def delete_for_bill(self, bill_id: UUID) -> None:
        self.session.execute(delete(Forecast).where(Forecast.bill_id == bill_id))

