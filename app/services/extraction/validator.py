from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.enums import BillExtractionStatus
from app.schemas.extraction import ExtractedBillData, HistoricalConsumptionEntry
from app.services.extraction.types import ParsedBillResult


@dataclass(slots=True)
class ValidationResult:
    structured_data: ExtractedBillData
    fields_for_review: list[str]
    extraction_status: BillExtractionStatus


class BillExtractionValidator:
    CORE_FIELDS = ("mes_referencia", "consumo_kwh", "valor_total")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate(self, parsed: ParsedBillResult) -> ValidationResult:
        confidence = {
            "concessionaria": parsed.concessionaria.confidence,
            "mes_referencia": parsed.mes_referencia.confidence,
            "consumo_kwh": parsed.consumo_kwh.confidence,
            "dias_faturados": parsed.dias_faturados.confidence,
            "valor_total": parsed.valor_total.confidence,
            "bandeira_tarifaria": parsed.bandeira_tarifaria.confidence,
            "unidade_consumidora": parsed.unidade_consumidora.confidence,
            "vencimento": parsed.vencimento.confidence,
            "historico_consumo": parsed.historico_consumo_confidence,
        }
        warnings = list(parsed.warnings)
        fields_for_review: set[str] = set()

        def review(field_name: str, message: str, *, confidence_override: float | None = None) -> None:
            fields_for_review.add(field_name)
            warnings.append(message)
            if confidence_override is not None:
                confidence[field_name] = min(confidence.get(field_name, 0.0), confidence_override)

        raw_dias_faturados = parsed.dias_faturados.value if isinstance(parsed.dias_faturados.value, int) else None
        dias_faturados = raw_dias_faturados
        if raw_dias_faturados is not None and not (0 <= raw_dias_faturados <= 60):
            dias_faturados = None
            review(
                "dias_faturados",
                "Dias faturados ficaram fora da faixa aceita e foram limpos para revisao.",
                confidence_override=0.0,
            )

        structured = ExtractedBillData(
            concessionaria=parsed.concessionaria.value if isinstance(parsed.concessionaria.value, str) else None,
            mes_referencia=parsed.mes_referencia.value if isinstance(parsed.mes_referencia.value, str) else None,
            consumo_kwh=parsed.consumo_kwh.value,
            dias_faturados=dias_faturados,
            valor_total=parsed.valor_total.value,
            bandeira_tarifaria=parsed.bandeira_tarifaria.value if isinstance(parsed.bandeira_tarifaria.value, str) else None,
            unidade_consumidora=parsed.unidade_consumidora.value if isinstance(parsed.unidade_consumidora.value, str) else None,
            vencimento=parsed.vencimento.value,
            historico_consumo=[],
            confidence=confidence,
            warnings=[],
        )

        if structured.consumo_kwh is None or structured.consumo_kwh <= 0:
            review("consumo_kwh", "Consumo em kWh nao foi identificado com seguranca.", confidence_override=0.0)

        if structured.valor_total is None or structured.valor_total <= 0:
            review("valor_total", "Valor total nao foi identificado com seguranca.", confidence_override=0.0)

        if not structured.mes_referencia:
            review("mes_referencia", "Mes de referencia nao foi identificado com seguranca.", confidence_override=0.0)

        if structured.dias_faturados is not None and not (20 <= structured.dias_faturados <= 40):
            review(
                "dias_faturados",
                "Dias faturados ficaram fora da faixa esperada de 20 a 40 dias.",
                confidence_override=0.4,
            )

        sorted_history = sorted(parsed.historico_consumo, key=lambda entry: entry.mes_referencia)
        if [entry.mes_referencia for entry in parsed.historico_consumo] != [entry.mes_referencia for entry in sorted_history]:
            review(
                "historico_consumo",
                "O historico de consumo foi reorganizado para manter a ordem cronologica.",
                confidence_override=0.55,
            )

        history_entries: list[HistoricalConsumptionEntry] = []
        for item in sorted_history:
            if item.consumo_kwh <= 0:
                review("historico_consumo", "Ha itens do historico com consumo invalido ou nao positivo.", confidence_override=0.3)
                continue
            history_dias_faturados = item.dias_faturados
            if history_dias_faturados is not None and not (0 <= history_dias_faturados <= 60):
                history_dias_faturados = None
                review(
                    "historico_consumo",
                    "Ha itens do historico com dias faturados fora da faixa aceita e eles foram limpos.",
                    confidence_override=0.3,
                )
            history_entries.append(
                HistoricalConsumptionEntry(
                    mes_referencia=item.mes_referencia,
                    consumo_kwh=item.consumo_kwh,
                    dias_faturados=history_dias_faturados,
                )
            )
        structured.historico_consumo = history_entries

        for field_name, score in confidence.items():
            if score < self.settings.low_confidence_threshold:
                review(field_name, f"Confira {self._friendly_field_name(field_name)}: a confianca da leitura ficou em {score:.2f}.")

        missing_core_fields = sum(1 for field_name in self.CORE_FIELDS if getattr(structured, field_name) in (None, ""))
        extraction_status = (
            BillExtractionStatus.FAILED
            if missing_core_fields == len(self.CORE_FIELDS) and not structured.historico_consumo
            else BillExtractionStatus.PENDING_REVIEW
        )
        structured.confidence = confidence
        structured.warnings = self._deduplicate(warnings)

        return ValidationResult(
            structured_data=structured,
            fields_for_review=sorted(fields_for_review),
            extraction_status=extraction_status,
        )

    @staticmethod
    def _deduplicate(values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                ordered.append(value)
        return ordered

    @staticmethod
    def _friendly_field_name(field_name: str) -> str:
        labels = {
            "concessionaria": "a concessionaria",
            "mes_referencia": "o mes de referencia",
            "consumo_kwh": "o consumo em kWh",
            "dias_faturados": "os dias faturados",
            "valor_total": "o valor total",
            "bandeira_tarifaria": "a bandeira tarifaria",
            "unidade_consumidora": "a unidade consumidora",
            "vencimento": "o vencimento",
            "historico_consumo": "o historico de consumo",
        }
        return labels.get(field_name, field_name.replace("_", " "))
