from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(slots=True)
class ParsedField:
    value: str | Decimal | int | date | None
    confidence: float
    source: str | None = None


@dataclass(slots=True)
class ParsedHistoryEntry:
    mes_referencia: str
    consumo_kwh: Decimal
    dias_faturados: int | None = None


@dataclass(slots=True)
class ParsedBillResult:
    concessionaria: ParsedField = field(default_factory=lambda: ParsedField(None, 0.0))
    mes_referencia: ParsedField = field(default_factory=lambda: ParsedField(None, 0.0))
    consumo_kwh: ParsedField = field(default_factory=lambda: ParsedField(None, 0.0))
    dias_faturados: ParsedField = field(default_factory=lambda: ParsedField(None, 0.0))
    valor_total: ParsedField = field(default_factory=lambda: ParsedField(None, 0.0))
    bandeira_tarifaria: ParsedField = field(default_factory=lambda: ParsedField(None, 0.0))
    unidade_consumidora: ParsedField = field(default_factory=lambda: ParsedField(None, 0.0))
    vencimento: ParsedField = field(default_factory=lambda: ParsedField(None, 0.0))
    historico_consumo: list[ParsedHistoryEntry] = field(default_factory=list)
    historico_consumo_confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TextExtractionResult:
    text: str
    method: str
    warnings: list[str] = field(default_factory=list)

