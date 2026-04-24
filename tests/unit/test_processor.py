from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.extraction.processor import BillProcessor
from app.services.extraction.types import ParsedBillResult, ParsedField, ParsedHistoryEntry


def test_processor_corrects_billed_days_from_labeled_date_range() -> None:
    processor = BillProcessor()
    parsed = ParsedBillResult(
        dias_faturados=ParsedField(250, 0.92, "Dias faturados: 250"),
    )
    text = """
    Periodo faturado: 02/03/2026 a 31/03/2026
    Dias faturados: 250
    """.strip()

    result = processor.process(parsed, text)

    assert result.dias_faturados.value == 30
    assert result.dias_faturados.confidence >= 0.82
    assert any("Dias faturados ajustados automaticamente para 30" in warning for warning in result.warnings)


def test_processor_corrects_truncated_consumption_from_labeled_line() -> None:
    processor = BillProcessor()
    parsed = ParsedBillResult(
        mes_referencia=ParsedField("2026-04", 0.95, "Mes de referencia: 04/2026"),
        consumo_kwh=ParsedField(Decimal("26"), 0.93, "Consumo Uso Sistema [KWh]-TUSD ABR/26 kWh 252,0000"),
        historico_consumo=[
            ParsedHistoryEntry(mes_referencia="2026-03", consumo_kwh=Decimal("336"), dias_faturados=32),
            ParsedHistoryEntry(mes_referencia="2026-04", consumo_kwh=Decimal("252"), dias_faturados=29),
        ],
    )
    text = """
    Mes de referencia: 04/2026
    Consumo Uso Sistema [KWh]-TUSD ABR/26 kWh 252,0000 0,44266000 0,57083334 143,85
    """.strip()

    result = processor.process(parsed, text)

    assert result.consumo_kwh.value == Decimal("252.0000")
    assert result.consumo_kwh.confidence >= 0.9
    assert any("Consumo em kWh ajustado automaticamente para 252.0000" in warning for warning in result.warnings)


def test_processor_infers_reference_month_from_due_date_when_missing() -> None:
    processor = BillProcessor()
    parsed = ParsedBillResult(
        mes_referencia=ParsedField(None, 0.0),
        vencimento=ParsedField(date(2026, 5, 15), 0.94, "Vencimento: 15/05/2026"),
    )

    result = processor.process(parsed, "Vencimento: 15/05/2026")

    assert result.mes_referencia.value == "2026-04"
    assert result.mes_referencia.confidence >= 0.72
    assert any("Mes de referencia inferido como 2026-04" in warning for warning in result.warnings)


def test_processor_preserves_existing_reference_month_when_only_history_suggests_another() -> None:
    processor = BillProcessor()
    parsed = ParsedBillResult(
        mes_referencia=ParsedField("2026-04", 0.72),
        historico_consumo=[
            ParsedHistoryEntry(mes_referencia="2026-04", consumo_kwh=Decimal("252"), dias_faturados=29),
            ParsedHistoryEntry(mes_referencia="2026-05", consumo_kwh=Decimal("228"), dias_faturados=28),
        ],
    )

    result = processor.process(parsed, "Referencia: 04/2026")

    assert result.mes_referencia.value == "2026-04"


def test_processor_uses_labeled_total_and_detects_tariff_flag() -> None:
    processor = BillProcessor()
    parsed = ParsedBillResult(
        valor_total=ParsedField(Decimal("198.45"), 0.40, "R$ 198,45"),
        bandeira_tarifaria=ParsedField(None, 0.0),
        historico_consumo=[
            ParsedHistoryEntry(mes_referencia="2026-03", consumo_kwh=Decimal("270"), dias_faturados=31),
            ParsedHistoryEntry(mes_referencia="2026-04", consumo_kwh=Decimal("252"), dias_faturados=29),
        ],
    )
    text = """
    Total a pagar: R$ 228,15
    Bandeira tarifaria: Verde
    """.strip()

    result = processor.process(parsed, text)

    assert result.valor_total.value == Decimal("228.15")
    assert result.valor_total.confidence >= 0.86
    assert result.bandeira_tarifaria.value == "Verde"
    assert result.bandeira_tarifaria.confidence >= 0.82


def test_processor_reconciles_history_with_primary_fields_for_reference_month() -> None:
    processor = BillProcessor()
    parsed = ParsedBillResult(
        mes_referencia=ParsedField("2026-04", 0.95, "Mes de referencia: 04/2026"),
        consumo_kwh=ParsedField(Decimal("252"), 0.93, "Consumo do mes: 252 kWh"),
        dias_faturados=ParsedField(29, 0.92, "Dias faturados: 29"),
        historico_consumo=[
            ParsedHistoryEntry(mes_referencia="2026-03", consumo_kwh=Decimal("336"), dias_faturados=32),
            ParsedHistoryEntry(mes_referencia="2026-04", consumo_kwh=Decimal("2"), dias_faturados=None),
        ],
        historico_consumo_confidence=0.72,
    )

    result = processor.process(parsed, "Mes de referencia: 04/2026\nConsumo do mes: 252 kWh")

    assert result.historico_consumo[-1].mes_referencia == "2026-04"
    assert result.historico_consumo[-1].consumo_kwh == Decimal("252")
    assert result.historico_consumo[-1].dias_faturados == 29
    assert any("Historico de consumo reconciliado" in warning for warning in result.warnings)
