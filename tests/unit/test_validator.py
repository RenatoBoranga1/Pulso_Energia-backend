from __future__ import annotations

from decimal import Decimal

from app.core.config import Settings
from app.core.enums import BillExtractionStatus
from app.services.extraction.types import ParsedBillResult, ParsedField, ParsedHistoryEntry
from app.services.extraction.validator import BillExtractionValidator


def test_validator_marks_invalid_core_fields_and_fails_when_nothing_usable() -> None:
    validator = BillExtractionValidator(Settings(low_confidence_threshold=0.75))
    parsed = ParsedBillResult(
        concessionaria=ParsedField(None, 0.0),
        mes_referencia=ParsedField(None, 0.0),
        consumo_kwh=ParsedField(None, 0.0),
        dias_faturados=ParsedField(10, 0.92),
        valor_total=ParsedField(None, 0.0),
        warnings=["Nao foi possivel identificar com seguranca os principais campos da conta."],
    )

    result = validator.validate(parsed)

    assert result.extraction_status == BillExtractionStatus.FAILED
    assert result.structured_data.mes_referencia is None
    assert result.structured_data.consumo_kwh is None
    assert result.structured_data.valor_total is None
    assert {"mes_referencia", "consumo_kwh", "valor_total", "dias_faturados"} <= set(result.fields_for_review)
    assert "Dias faturados ficaram fora da faixa esperada de 20 a 40 dias." in result.structured_data.warnings


def test_validator_reorders_history_and_flags_low_confidence_history() -> None:
    validator = BillExtractionValidator(Settings(low_confidence_threshold=0.75))
    parsed = ParsedBillResult(
        concessionaria=ParsedField("Enel", 0.95),
        mes_referencia=ParsedField("2026-04", 0.95),
        consumo_kwh=ParsedField(Decimal("252"), 0.93),
        dias_faturados=ParsedField(29, 0.92),
        valor_total=ParsedField(Decimal("198.45"), 0.94),
        historico_consumo=[
            ParsedHistoryEntry(mes_referencia="2026-03", consumo_kwh=Decimal("336"), dias_faturados=32),
            ParsedHistoryEntry(mes_referencia="2026-01", consumo_kwh=Decimal("336"), dias_faturados=29),
            ParsedHistoryEntry(mes_referencia="2026-02", consumo_kwh=Decimal("-1"), dias_faturados=28),
        ],
        historico_consumo_confidence=0.7,
    )

    result = validator.validate(parsed)

    assert result.extraction_status == BillExtractionStatus.PENDING_REVIEW
    assert [item.mes_referencia for item in result.structured_data.historico_consumo] == ["2026-01", "2026-03"]
    assert "historico_consumo" in result.fields_for_review
    assert "O historico de consumo foi reorganizado para manter a ordem cronologica." in result.structured_data.warnings
    assert "Ha itens do historico com consumo invalido ou nao positivo." in result.structured_data.warnings
    assert result.structured_data.confidence["historico_consumo"] <= 0.3


def test_validator_clears_schema_invalid_billed_days_instead_of_crashing() -> None:
    validator = BillExtractionValidator(Settings(low_confidence_threshold=0.75))
    parsed = ParsedBillResult(
        concessionaria=ParsedField("CPFL", 0.95),
        mes_referencia=ParsedField("2026-04", 0.95),
        consumo_kwh=ParsedField(Decimal("252"), 0.93),
        dias_faturados=ParsedField(250, 0.92),
        valor_total=ParsedField(Decimal("198.45"), 0.94),
        historico_consumo=[
            ParsedHistoryEntry(mes_referencia="2026-03", consumo_kwh=Decimal("336"), dias_faturados=250),
        ],
    )

    result = validator.validate(parsed)

    assert result.extraction_status == BillExtractionStatus.PENDING_REVIEW
    assert result.structured_data.dias_faturados is None
    assert result.structured_data.historico_consumo[0].dias_faturados is None
    assert "dias_faturados" in result.fields_for_review
    assert "historico_consumo" in result.fields_for_review
    assert "Dias faturados ficaram fora da faixa aceita e foram limpos para revisao." in result.structured_data.warnings
    assert "Ha itens do historico com dias faturados fora da faixa aceita e eles foram limpos." in result.structured_data.warnings
