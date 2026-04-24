from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import BillExtractionStatus
from app.models.utility_bill import UtilityBill


class UtilityBillRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, bill_id: UUID) -> UtilityBill | None:
        return self._execute_detail_query(select(UtilityBill).where(UtilityBill.id == bill_id))

    def get_by_id_for_user(self, bill_id: UUID, user_id: UUID) -> UtilityBill | None:
        return self._execute_detail_query(
            select(UtilityBill).where(
                UtilityBill.id == bill_id,
                UtilityBill.user_id == user_id,
            )
        )

    def _execute_detail_query(self, statement):
        statement = (
            statement
            .options(
                selectinload(UtilityBill.document),
                selectinload(UtilityBill.consumption_history),
                selectinload(UtilityBill.confidence_scores),
                selectinload(UtilityBill.forecasts),
                selectinload(UtilityBill.insights),
            )
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_document_id(self, document_id: UUID) -> UtilityBill | None:
        statement = (
            select(UtilityBill)
            .options(
                selectinload(UtilityBill.document),
                selectinload(UtilityBill.consumption_history),
                selectinload(UtilityBill.confidence_scores),
                selectinload(UtilityBill.forecasts),
                selectinload(UtilityBill.insights),
            )
            .where(UtilityBill.document_id == document_id)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_by_user_id(self, user_id: UUID) -> list[UtilityBill]:
        statement = (
            select(UtilityBill)
            .options(
                selectinload(UtilityBill.consumption_history),
                selectinload(UtilityBill.forecasts),
                selectinload(UtilityBill.insights),
            )
            .where(UtilityBill.user_id == user_id)
            .order_by(UtilityBill.created_at.desc(), UtilityBill.id.desc())
        )
        return list(self.session.execute(statement).scalars().all())

    def list_confirmed_by_user_id(self, user_id: UUID) -> list[UtilityBill]:
        statement = (
            select(UtilityBill)
            .options(selectinload(UtilityBill.consumption_history))
            .where(
                UtilityBill.user_id == user_id,
                UtilityBill.extraction_status == BillExtractionStatus.CONFIRMED,
            )
            .order_by(UtilityBill.created_at.desc(), UtilityBill.id.desc())
        )
        return list(self.session.execute(statement).scalars().all())

    def save(self, bill: UtilityBill) -> UtilityBill:
        self.session.add(bill)
        self.session.flush()
        self.session.refresh(bill)
        return bill

    def delete(self, bill: UtilityBill) -> None:
        self.session.delete(bill)
        self.session.flush()
