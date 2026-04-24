from __future__ import annotations

from decimal import Decimal

from app.services.extraction.parser import BillSemanticParser


def test_semantic_parser_extracts_main_fields_and_history() -> None:
    parser = BillSemanticParser()
    text = """
    Concessionaria: Enel Sao Paulo
    Mes de referencia: 04/2026
    Consumo do mes: 252 kWh
    Dias faturados: 29
    Valor total: R$ 198,45
    Bandeira tarifaria: Verde
    Unidade Consumidora: 123456789
    Vencimento: 15/05/2026
    Historico de consumo
    2026-01 336 29
    2026-02 267 28
    2026-03 336 32
    2026-04 252 29
    """.strip()

    result = parser.parse(text)

    assert result.concessionaria.value == "Enel Sao Paulo"
    assert result.mes_referencia.value == "2026-04"
    assert result.consumo_kwh.value == Decimal("252")
    assert result.dias_faturados.value == 29
    assert result.valor_total.value == Decimal("198.45")
    assert result.unidade_consumidora.value == "123456789"
    assert len(result.historico_consumo) == 4
    assert result.historico_consumo[0].mes_referencia == "2026-01"


def test_semantic_parser_does_not_treat_due_date_as_history_entry() -> None:
    parser = BillSemanticParser()
    text = """
    Concessionaria: Enel Sao Paulo
    Referencia: 04/2026
    Vencimento: 15/05/2026
    Total a pagar: R$ 210,30
    """.strip()

    result = parser.parse(text)

    assert result.mes_referencia.value == "2026-04"
    assert result.vencimento.value is not None
    assert result.historico_consumo == []


def test_semantic_parser_emits_warning_for_empty_text() -> None:
    parser = BillSemanticParser()

    result = parser.parse("   ")

    assert "Nao foi possivel extrair texto legivel do documento." in result.warnings
    assert "Nao foi possivel identificar com seguranca os principais campos da conta." in result.warnings


def test_semantic_parser_prefers_consumption_after_kwh_unit_when_reference_month_precedes_it() -> None:
    parser = BillSemanticParser()
    text = """
    Mes de referencia: 04/2026
    Consumo Uso Sistema [KWh]-TUSD ABR/26 kWh 252,0000 0,44266000 0,57083334 143,85
    Valor total: R$ 228,15
    """.strip()

    result = parser.parse(text)

    assert result.mes_referencia.value == "2026-04"
    assert result.consumo_kwh.value == Decimal("252.0000")


def test_semantic_parser_extracts_history_rows_with_month_abbreviation_and_two_digit_year() -> None:
    parser = BillSemanticParser()
    text = """
    ABR 26 llllllllllllllllllllllllllllllllllllllllllllllllllllllll 252 29
    MAR 26 lllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllll 336 32
    DEZ 25 lllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllll 301 33
    NOV 25 lllllllllllllllllllllllllllllllllllllllllllllllll 218 29
    OUT 25 lllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllll 334 29
    SET 25 llllllllllllllllllllllllllllllllllllllllllllllllllllllllll 260 33
    AGO 25 llllllllllllllllllllllllllllllllllllllllllllllllllllll 240 31
    MAI 25 lllllllllllllllllllllllllllllllllllllllllllllllllll 230 31
    ABR 25 lllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllll 280 28
    """.strip()

    result = parser.parse(text)

    assert [item.mes_referencia for item in result.historico_consumo] == [
        "2025-04",
        "2025-05",
        "2025-08",
        "2025-09",
        "2025-10",
        "2025-11",
        "2025-12",
        "2026-03",
        "2026-04",
    ]
    assert result.historico_consumo[-1].consumo_kwh == Decimal("252")
    assert result.historico_consumo[-1].dias_faturados == 29


def test_semantic_parser_recovers_interleaved_history_rows_from_ocr_fragmentation() -> None:
    parser = BillSemanticParser()
    text = """
    ABR 26 llllllllllllllllllllllllllllllllllllllllllllllllllllllll 252 29
    MAR 26 lllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllll 336 32
    F
    JA
    E
    N
    V
    2
    2
    6
    6 l
    lllllllllllllll
    2
    3
    6
    3
    7
    6
    2
    2
    8
    9
    DEZ 25 lllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllll 301 33
    NOV 25 lllllllllllllllllllllllllllllllllllllllllllllllll 218 29
    OUT 25 lllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllll 334 29
    SET 25 llllllllllllllllllllllllllllllllllllllllllllllllllllllllll 260 33
    AGO 25 llllllllllllllllllllllllllllllllllllllllllllllllllllll 240 31
    J
    J
    U
    U
    L
    N
    2
    2
    5
    5
    lllllllllllll 2
    2
    7
    1
    0
    0
    3
    2
    2
    9
    MAI 25 lllllllllllllllllllllllllllllllllllllllllllllllllll 230 31
    ABR 25 lllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllll 280 28
    """.strip()

    result = parser.parse(text)

    assert [item.mes_referencia for item in result.historico_consumo] == [
        "2025-04",
        "2025-05",
        "2025-06",
        "2025-07",
        "2025-08",
        "2025-09",
        "2025-10",
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
    ]
    assert [str(item.consumo_kwh) for item in result.historico_consumo[-4:]] == ["336", "267", "336", "252"]
    assert [item.dias_faturados for item in result.historico_consumo[-4:]] == [29, 28, 32, 29]
