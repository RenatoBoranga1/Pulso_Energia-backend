from __future__ import annotations

from app.schemas.bill import ConsumptionHistoryRead, ExtractionConfidenceRead, UtilityBillDetailRead
from app.schemas.document import UploadedDocumentRead
from app.schemas.extraction import BillReviewResponse, ExtractedBillData
from app.schemas.extraction_log import ExtractionLogRead


def build_bill_review_response(*, bill, logs, low_confidence_threshold: float) -> BillReviewResponse:
    confidence_map = {
        item.field_name: float(item.confidence_score)
        for item in bill.confidence_scores
    }
    warnings = [
        log.message
        for log in logs
        if log.level.value in {"WARNING", "ERROR"}
    ]
    structured_data = ExtractedBillData(
        concessionaria=bill.concessionaria,
        mes_referencia=bill.mes_referencia,
        consumo_kwh=bill.consumo_kwh,
        dias_faturados=bill.dias_faturados,
        valor_total=bill.valor_total,
        bandeira_tarifaria=bill.bandeira_tarifaria,
        unidade_consumidora=bill.unidade_consumidora,
        vencimento=bill.vencimento,
        historico_consumo=[
            {
                "mes_referencia": item.mes_referencia,
                "consumo_kwh": item.consumo_kwh,
                "dias_faturados": item.dias_faturados,
            }
            for item in bill.consumption_history
        ],
        confidence=confidence_map,
        warnings=warnings,
    )
    fields_for_review = (
        []
        if not bill.review_required
        else sorted(field_name for field_name, score in confidence_map.items() if score < low_confidence_threshold)
    )
    return BillReviewResponse(
        bill_id=bill.id,
        document=UploadedDocumentRead.model_validate(bill.document),
        extraction_status=bill.extraction_status,
        review_required=bill.review_required,
        structured_data=structured_data,
        fields_for_review=fields_for_review,
        bill=UtilityBillDetailRead(
            id=bill.id,
            user_id=bill.user_id,
            document_id=bill.document_id,
            concessionaria=bill.concessionaria,
            mes_referencia=bill.mes_referencia,
            consumo_kwh=bill.consumo_kwh,
            dias_faturados=bill.dias_faturados,
            valor_total=bill.valor_total,
            bandeira_tarifaria=bill.bandeira_tarifaria,
            unidade_consumidora=bill.unidade_consumidora,
            vencimento=bill.vencimento,
            extraction_status=bill.extraction_status,
            review_required=bill.review_required,
            created_at=bill.created_at,
            document=UploadedDocumentRead.model_validate(bill.document),
            consumption_history=[ConsumptionHistoryRead.model_validate(item) for item in bill.consumption_history],
            confidence_scores=[ExtractionConfidenceRead.model_validate(item) for item in bill.confidence_scores],
        ),
        logs=[ExtractionLogRead.model_validate(log) for log in logs],
    )
