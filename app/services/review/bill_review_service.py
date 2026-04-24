from __future__ import annotations

import logging
from uuid import UUID

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import BillExtractionStatus, ExtractionLogLevel, ExtractionLogStage
from app.core.errors import AppError
from app.models.consumption_history import ConsumptionHistory
from app.repositories.extraction_log_repository import ExtractionLogRepository
from app.repositories.user_repository import UserRepository
from app.repositories.utility_bill_repository import UtilityBillRepository
from app.schemas.extraction import BillReviewResponse, ConfirmBillRequest, UserBillHistoryEntry, UserBillHistoryResponse
from app.services.analytics.service import BillAnalyticsService
from app.services.extraction.response_builder import build_bill_review_response


logger = logging.getLogger(__name__)


class BillReviewService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.bill_repository = UtilityBillRepository(session)
        self.log_repository = ExtractionLogRepository(session)
        self.user_repository = UserRepository(session)

    def confirm(self, *, bill_id: UUID, payload: ConfirmBillRequest, current_user_id: UUID) -> BillReviewResponse:
        bill = self.bill_repository.get_by_id_for_user(bill_id, current_user_id)
        if bill is None:
            raise AppError("Bill not found.", code="bill_not_found", status_code=status.HTTP_404_NOT_FOUND)

        data = payload.data
        bill.concessionaria = data.concessionaria
        bill.mes_referencia = data.mes_referencia
        bill.consumo_kwh = data.consumo_kwh
        bill.dias_faturados = data.dias_faturados
        bill.valor_total = data.valor_total
        bill.bandeira_tarifaria = data.bandeira_tarifaria
        bill.unidade_consumidora = data.unidade_consumidora
        bill.vencimento = data.vencimento
        bill.forecasts.clear()
        bill.insights.clear()
        bill.consumption_history.clear()
        self.session.flush()
        bill.consumption_history.extend(
            [
                ConsumptionHistory(
                    mes_referencia=item.mes_referencia,
                    consumo_kwh=item.consumo_kwh,
                    dias_faturados=item.dias_faturados,
                )
                for item in data.historico_consumo
            ]
        )
        bill.extraction_status = BillExtractionStatus.CONFIRMED
        bill.review_required = False
        self.bill_repository.save(bill)
        self.log_repository.add(
            document_id=bill.document_id,
            bill_id=bill.id,
            stage=ExtractionLogStage.REVIEW,
            level=ExtractionLogLevel.INFO,
            message="Bill confirmed by manual review.",
            source_component="bill_review_service",
        )
        self.session.commit()
        try:
            BillAnalyticsService(session=self.session, settings=self.settings).refresh_artifacts_for_bill(
                bill_id=bill.id,
                current_user_id=current_user_id,
            )
        except Exception:
            logger.exception(
                "Failed to refresh derived bill artifacts after confirmation",
                extra={"event": "bill_artifact_refresh_failed", "bill_id": str(bill.id)},
            )

        refreshed = self.bill_repository.get_by_id(bill.id)
        if refreshed is None:
            raise AppError("Confirmed bill could not be reloaded.", code="bill_reload_error", status_code=500)
        logs = self.log_repository.list_for_document(refreshed.document_id)
        return build_bill_review_response(
            bill=refreshed,
            logs=logs,
            low_confidence_threshold=self.settings.low_confidence_threshold,
        )

    def list_user_history(self, *, user_id: UUID, current_user_id: UUID) -> UserBillHistoryResponse:
        if user_id != current_user_id:
            raise AppError(
                "You cannot access another user's history.",
                code="forbidden",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise AppError("User not found.", code="user_not_found", status_code=status.HTTP_404_NOT_FOUND)

        bills = self.bill_repository.list_by_user_id(user_id)
        return UserBillHistoryResponse(
            user_id=user.id,
            bills=[
                UserBillHistoryEntry(
                    bill_id=bill.id,
                    document_id=bill.document_id,
                    mes_referencia=bill.mes_referencia,
                    concessionaria=bill.concessionaria,
                    consumo_kwh=bill.consumo_kwh,
                    valor_total=bill.valor_total,
                    extraction_status=bill.extraction_status,
                    review_required=bill.review_required,
                )
                for bill in bills
            ],
        )
