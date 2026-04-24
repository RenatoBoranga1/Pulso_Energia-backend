from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import ExtractionLogLevel, ExtractionLogStage
from app.core.errors import AppError
from app.models.consumption_history import ConsumptionHistory
from app.models.extraction_confidence import ExtractionConfidence
from app.models.utility_bill import UtilityBill
from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_log_repository import ExtractionLogRepository
from app.repositories.utility_bill_repository import UtilityBillRepository
from app.schemas.extraction import BillReviewResponse
from app.services.extraction.normalizer import TextNormalizationService
from app.services.extraction.parser import BillSemanticParser
from app.services.extraction.processor import BillProcessor
from app.services.extraction.response_builder import build_bill_review_response
from app.services.extraction.text_extractor import DocumentTextExtractionService
from app.services.extraction.validator import BillExtractionValidator


class BillExtractionService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.document_repository = DocumentRepository(session)
        self.bill_repository = UtilityBillRepository(session)
        self.log_repository = ExtractionLogRepository(session)
        self.text_extractor = DocumentTextExtractionService(settings)
        self.normalizer = TextNormalizationService()
        self.parser = BillSemanticParser()
        self.processor = BillProcessor()
        self.validator = BillExtractionValidator(settings)

    def extract(self, *, document_id: UUID, current_user_id: UUID) -> BillReviewResponse:
        document = self.document_repository.get_by_id_for_user(document_id, current_user_id)
        if document is None:
            raise AppError(
                "Document not found.",
                code="document_not_found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        extraction_result = self.text_extractor.extract(document)
        self.log_repository.add(
            document_id=document.id,
            bill_id=None,
            stage=ExtractionLogStage.TEXT_EXTRACTION,
            level=ExtractionLogLevel.INFO,
            message=f"Text extracted using method '{extraction_result.method}'.",
            source_component="document_text_extraction_service",
        )
        for warning in extraction_result.warnings:
            self.log_repository.add(
                document_id=document.id,
                bill_id=None,
                stage=ExtractionLogStage.TEXT_EXTRACTION,
                level=ExtractionLogLevel.WARNING,
                message=warning,
                source_component="document_text_extraction_service",
            )

        normalized_text = self.normalizer.normalize(extraction_result.text)
        document.extracted_text = normalized_text
        self.document_repository.save(document)
        self.log_repository.add(
            document_id=document.id,
            bill_id=None,
            stage=ExtractionLogStage.NORMALIZATION,
            level=ExtractionLogLevel.INFO,
            message="Extracted text normalized successfully.",
            source_component="text_normalization_service",
        )

        parsed = self.parser.parse(normalized_text)
        self.log_repository.add(
            document_id=document.id,
            bill_id=None,
            stage=ExtractionLogStage.SEMANTIC_PARSING,
            level=ExtractionLogLevel.INFO,
            message="Semantic parsing completed.",
            source_component="bill_semantic_parser",
        )
        parsed = self.processor.process(parsed, normalized_text)
        self.log_repository.add(
            document_id=document.id,
            bill_id=None,
            stage=ExtractionLogStage.VALIDATION,
            level=ExtractionLogLevel.INFO,
            message="Post-processing rules applied to extraction payload.",
            source_component="bill_processor",
        )

        validation = self.validator.validate(parsed)
        bill = self._upsert_bill(document=document, validation=validation)
        self._log_validation(document_id=document.id, bill_id=bill.id, warnings=validation.structured_data.warnings)
        self.session.commit()

        persisted_bill = self.bill_repository.get_by_document_id(document.id)
        if persisted_bill is None:
            raise AppError("Bill extraction did not persist a bill record.", code="bill_persistence_error", status_code=500)
        logs = self.log_repository.list_for_document(document.id)
        return build_bill_review_response(
            bill=persisted_bill,
            logs=logs,
            low_confidence_threshold=self.settings.low_confidence_threshold,
        )

    def get_bill_review(self, *, bill_id: UUID, current_user_id: UUID) -> BillReviewResponse:
        bill = self.bill_repository.get_by_id_for_user(bill_id, current_user_id)
        if bill is None:
            raise AppError("Bill not found.", code="bill_not_found", status_code=status.HTTP_404_NOT_FOUND)
        logs = self.log_repository.list_for_document(bill.document_id)
        return build_bill_review_response(
            bill=bill,
            logs=logs,
            low_confidence_threshold=self.settings.low_confidence_threshold,
        )

    def _upsert_bill(self, *, document, validation) -> UtilityBill:
        bill = self.bill_repository.get_by_document_id(document.id)
        if bill is None:
            bill = UtilityBill(user_id=document.user_id, document_id=document.id)

        structured_data = validation.structured_data
        bill.concessionaria = structured_data.concessionaria
        bill.mes_referencia = structured_data.mes_referencia
        bill.consumo_kwh = structured_data.consumo_kwh
        bill.dias_faturados = structured_data.dias_faturados
        bill.valor_total = structured_data.valor_total
        bill.bandeira_tarifaria = structured_data.bandeira_tarifaria
        bill.unidade_consumidora = structured_data.unidade_consumidora
        bill.vencimento = structured_data.vencimento
        bill.extraction_status = validation.extraction_status
        bill.review_required = True
        bill.forecasts.clear()
        bill.insights.clear()
        bill.consumption_history.clear()
        bill.confidence_scores.clear()
        self.session.flush()
        bill.consumption_history.extend(
            [
                ConsumptionHistory(
                    mes_referencia=item.mes_referencia,
                    consumo_kwh=item.consumo_kwh,
                    dias_faturados=item.dias_faturados,
                )
                for item in structured_data.historico_consumo
            ]
        )
        bill.confidence_scores.extend(
            [
                ExtractionConfidence(
                    field_name=field_name,
                    confidence_score=Decimal(f"{score:.4f}"),
                )
                for field_name, score in structured_data.confidence.items()
            ]
        )
        self.bill_repository.save(bill)
        return bill

    def _log_validation(self, *, document_id, bill_id, warnings: list[str]) -> None:
        self.log_repository.add(
            document_id=document_id,
            bill_id=bill_id,
            stage=ExtractionLogStage.VALIDATION,
            level=ExtractionLogLevel.INFO,
            message="Validation completed and extraction payload persisted.",
            source_component="bill_extraction_validator",
        )
        for warning in warnings:
            self.log_repository.add(
                document_id=document_id,
                bill_id=bill_id,
                stage=ExtractionLogStage.VALIDATION,
                level=ExtractionLogLevel.WARNING,
                message=warning,
                source_component="bill_extraction_validator",
            )
