from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.insight import Insight


class InsightRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_bill_id(self, bill_id: UUID) -> list[Insight]:
        statement = (
            select(Insight)
            .where(Insight.bill_id == bill_id)
            .order_by(Insight.created_at.asc(), Insight.id.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    def replace_for_bill(self, *, bill_id: UUID, insights: list[Insight]) -> list[Insight]:
        self.delete_for_bill(bill_id)
        for insight in insights:
            insight.bill_id = bill_id
            self.session.add(insight)
        self.session.flush()
        return insights

    def delete_for_bill(self, bill_id: UUID) -> None:
        self.session.execute(delete(Insight).where(Insight.bill_id == bill_id))

