from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from app.services.extraction.types import ParsedBillResult, ParsedField, ParsedHistoryEntry
from app.utils.datetime import parse_brazilian_date
from app.utils.numbers import parse_decimal
from app.utils.reference_month import parse_reference_month
from app.utils.text import clean_line_tokens, normalize_for_matching


class BillProcessor:
    """Applies deterministic post-processing rules before final validation."""

    PLAUSIBLE_BILLED_DAYS_RANGE = range(20, 36)
    ACCEPTED_BILLED_DAYS_RANGE = range(0, 61)

    TOTAL_LABELS = (
        "total a pagar",
        "valor total",
        "valor da fatura",
        "valor da conta",
        "total da fatura",
        "total geral",
    )
    REFERENCE_LABELS = (
        "mes de referencia",
        "referencia",
        "competencia",
        "referente a",
        "mes ref",
    )
    DAY_LABELS = (
        "dias faturados",
        "dias de faturamento",
        "periodo faturado",
        "periodo de faturamento",
    )
    CONSUMPTION_LABELS = (
        "consumo do mes",
        "consumo uso sistema",
        "energia consumida",
        "consumo - te",
        "consumo",
    )
    TARIFF_FLAGS = (
        ("vermelha patamar 2", "Vermelha patamar 2"),
        ("vermelha patamar 1", "Vermelha patamar 1"),
        ("bandeira vermelha", "Vermelha"),
        ("vermelha", "Vermelha"),
        ("bandeira amarela", "Amarela"),
        ("amarela", "Amarela"),
        ("bandeira verde", "Verde"),
        ("verde", "Verde"),
        ("escassez hidrica", "Escassez hidrica"),
    )

    def process(self, parsed: ParsedBillResult, text: str) -> ParsedBillResult:
        lines = clean_line_tokens(text.splitlines())
        normalized_lines = [normalize_for_matching(line) for line in lines]

        self._correct_consumption_kwh(parsed, lines, normalized_lines)
        self._correct_billed_days(parsed, lines, normalized_lines)
        self._infer_reference_month(parsed, lines, normalized_lines)
        self._fallback_total_value(parsed, lines, normalized_lines)
        self._fallback_tariff_flag(parsed, lines, normalized_lines)
        self._reconcile_history_with_primary_fields(parsed)

        return parsed

    def _correct_consumption_kwh(
        self,
        parsed: ParsedBillResult,
        lines: list[str],
        normalized_lines: list[str],
    ) -> None:
        current = parsed.consumo_kwh.value if isinstance(parsed.consumo_kwh.value, Decimal) else None
        candidate = self._extract_labeled_consumption(lines, normalized_lines)
        if candidate is None:
            candidate = self._extract_current_month_history_consumption(parsed)

        if candidate is None:
            return

        if current == candidate:
            return

        if current is None or current <= 0 or self._should_replace_consumption(current=current, candidate=candidate):
            parsed.consumo_kwh = ParsedField(
                candidate,
                max(parsed.consumo_kwh.confidence, 0.9),
                "bill_processor:consumption_kwh",
            )
            parsed.warnings.append(
                f"Consumo em kWh ajustado automaticamente para {candidate} com base na linha principal de consumo."
            )

    def _correct_billed_days(
        self,
        parsed: ParsedBillResult,
        lines: list[str],
        normalized_lines: list[str],
    ) -> None:
        current = parsed.dias_faturados.value
        current_is_valid = isinstance(current, int) and current in self.PLAUSIBLE_BILLED_DAYS_RANGE
        if current_is_valid and parsed.dias_faturados.confidence >= 0.75:
            return

        candidate = self._extract_labeled_billed_days(lines, normalized_lines)
        if candidate is None:
            candidate = self._infer_days_from_history(parsed)

        if candidate is not None:
            parsed.dias_faturados = ParsedField(
                candidate,
                max(parsed.dias_faturados.confidence, 0.82),
                "bill_processor:billed_days",
            )
            if current != candidate:
                parsed.warnings.append(
                    f"Dias faturados ajustados automaticamente para {candidate} com base em padroes da fatura."
                )
            return

        if isinstance(current, int) and current not in self.ACCEPTED_BILLED_DAYS_RANGE:
            parsed.dias_faturados = ParsedField(None, 0.0, parsed.dias_faturados.source)
            parsed.warnings.append(
                "Dias faturados pareciam inconsistentes e foram deixados em branco para revisao."
            )

    def _infer_reference_month(
        self,
        parsed: ParsedBillResult,
        lines: list[str],
        normalized_lines: list[str],
    ) -> None:
        current = parsed.mes_referencia.value
        labeled_month = self._extract_labeled_reference_month(lines, normalized_lines)
        if labeled_month:
            parsed.mes_referencia = ParsedField(
                labeled_month,
                max(parsed.mes_referencia.confidence, 0.88),
                "bill_processor:labeled_reference_month",
            )
            return

        if isinstance(current, str):
            return

        history_month = parsed.historico_consumo[-1].mes_referencia if parsed.historico_consumo else None
        if history_month:
            parsed.mes_referencia = ParsedField(
                history_month,
                max(parsed.mes_referencia.confidence, 0.78),
                "bill_processor:history_latest_month",
            )
            parsed.warnings.append(
                f"Mes de referencia inferido como {history_month} a partir do historico de consumo."
            )
            return

        due_date = parsed.vencimento.value
        if isinstance(due_date, date):
            reference_month = self._previous_month(due_date)
            parsed.mes_referencia = ParsedField(
                reference_month,
                max(parsed.mes_referencia.confidence, 0.72),
                "bill_processor:due_date_previous_month",
            )
            parsed.warnings.append(
                f"Mes de referencia inferido como {reference_month} a partir da data de vencimento."
            )

    def _fallback_total_value(
        self,
        parsed: ParsedBillResult,
        lines: list[str],
        normalized_lines: list[str],
    ) -> None:
        if isinstance(parsed.valor_total.value, Decimal) and parsed.valor_total.confidence >= 0.75:
            return

        candidate = self._extract_labeled_total_value(lines, normalized_lines)
        if candidate is None:
            return

        if candidate != parsed.valor_total.value:
            parsed.warnings.append(
                f"Valor total ajustado para R$ {candidate} usando rotulo de total da fatura."
            )
        parsed.valor_total = ParsedField(
            candidate,
            max(parsed.valor_total.confidence, 0.86),
            "bill_processor:total_value_fallback",
        )

    def _fallback_tariff_flag(
        self,
        parsed: ParsedBillResult,
        lines: list[str],
        normalized_lines: list[str],
    ) -> None:
        if isinstance(parsed.bandeira_tarifaria.value, str) and parsed.bandeira_tarifaria.confidence >= 0.75:
            return

        flag = self._extract_tariff_flag(lines, normalized_lines)
        if flag:
            parsed.bandeira_tarifaria = ParsedField(
                flag,
                max(parsed.bandeira_tarifaria.confidence, 0.82),
                "bill_processor:tariff_flag",
            )
            return

        if any("bandeira" in normalized for normalized in normalized_lines):
            parsed.bandeira_tarifaria = ParsedField(
                "Nao identificada",
                max(parsed.bandeira_tarifaria.confidence, 0.45),
                "bill_processor:tariff_flag_not_found",
            )
            parsed.warnings.append(
                "A fatura menciona bandeira tarifaria, mas nao foi possivel identificar a cor com seguranca."
            )

    def _extract_labeled_billed_days(self, lines: list[str], normalized_lines: list[str]) -> int | None:
        for line, normalized in zip(lines, normalized_lines, strict=False):
            if not any(label in normalized for label in self.DAY_LABELS):
                continue

            range_days = self._extract_days_from_date_range(line)
            if range_days in self.PLAUSIBLE_BILLED_DAYS_RANGE:
                return range_days

            integers = [int(match) for match in re.findall(r"\b\d{1,3}\b", line)]
            plausible = [number for number in integers if number in self.PLAUSIBLE_BILLED_DAYS_RANGE]
            if plausible:
                return plausible[-1]

        return None

    def _extract_days_from_date_range(self, line: str) -> int | None:
        dates = [parse_brazilian_date(match) for match in re.findall(r"\d{2}/\d{2}/\d{2,4}", line)]
        dates = [value for value in dates if value is not None]
        if len(dates) < 2:
            return None
        days = (dates[1] - dates[0]).days + 1
        return days if days in self.PLAUSIBLE_BILLED_DAYS_RANGE else None

    def _infer_days_from_history(self, parsed: ParsedBillResult) -> int | None:
        candidates = [
            item.dias_faturados
            for item in parsed.historico_consumo
            if item.dias_faturados in self.PLAUSIBLE_BILLED_DAYS_RANGE
        ]
        if not candidates:
            return None
        ordered = sorted(candidates)
        return ordered[len(ordered) // 2]

    def _extract_labeled_consumption(self, lines: list[str], normalized_lines: list[str]) -> Decimal | None:
        for line, normalized in zip(lines, normalized_lines, strict=False):
            if "kwh" not in normalized:
                continue
            if not any(label in normalized for label in self.CONSUMPTION_LABELS):
                continue

            candidates = self._extract_consumption_candidates_from_line(line)
            if candidates:
                return max(candidates)

        return None

    def _extract_current_month_history_consumption(self, parsed: ParsedBillResult) -> Decimal | None:
        reference_month = parsed.mes_referencia.value if isinstance(parsed.mes_referencia.value, str) else None
        if not reference_month:
            return None

        for item in parsed.historico_consumo:
            if item.mes_referencia == reference_month and item.consumo_kwh > 0:
                return item.consumo_kwh
        return None

    def _extract_consumption_candidates_from_line(self, line: str) -> list[Decimal]:
        candidates: list[Decimal] = []
        for match in re.finditer(r"\bkwh\b", line, re.IGNORECASE):
            segment = line[match.end() : match.end() + 40]
            number_match = re.search(r"[^\d]{0,6}(\d{1,5}(?:[.,]\d{1,4})?)", segment)
            if not number_match:
                continue
            candidate = parse_decimal(number_match.group(1))
            if candidate is not None and candidate > 0:
                candidates.append(candidate)

        before_match = re.search(r"(\d{1,5}(?:[.,]\d{1,4})?)\s*kwh\b", line, re.IGNORECASE)
        if before_match:
            candidate = parse_decimal(before_match.group(1))
            if candidate is not None and candidate > 0:
                candidates.append(candidate)

        return candidates

    def _should_replace_consumption(self, *, current: Decimal, candidate: Decimal) -> bool:
        if current < Decimal("100") <= candidate:
            return True

        smaller = min(current, candidate)
        larger = max(current, candidate)
        if smaller == 0:
            return True

        return (larger / smaller) >= Decimal("3")

    def _reconcile_history_with_primary_fields(self, parsed: ParsedBillResult) -> None:
        reference_month = parsed.mes_referencia.value if isinstance(parsed.mes_referencia.value, str) else None
        consumo_kwh = parsed.consumo_kwh.value if isinstance(parsed.consumo_kwh.value, Decimal) else None
        dias_faturados = parsed.dias_faturados.value if isinstance(parsed.dias_faturados.value, int) else None

        if reference_month is None or consumo_kwh is None or consumo_kwh <= 0:
            return

        updated = False
        for index, item in enumerate(parsed.historico_consumo):
            if item.mes_referencia != reference_month:
                continue

            if item.consumo_kwh != consumo_kwh or item.dias_faturados != dias_faturados:
                parsed.historico_consumo[index] = ParsedHistoryEntry(
                    mes_referencia=reference_month,
                    consumo_kwh=consumo_kwh,
                    dias_faturados=dias_faturados,
                )
                updated = True
            break
        else:
            parsed.historico_consumo.append(
                ParsedHistoryEntry(
                    mes_referencia=reference_month,
                    consumo_kwh=consumo_kwh,
                    dias_faturados=dias_faturados,
                )
            )
            updated = True

        if updated:
            parsed.historico_consumo.sort(key=lambda item: item.mes_referencia)
            parsed.historico_consumo_confidence = max(parsed.historico_consumo_confidence, 0.82)
            parsed.warnings.append(
                "Historico de consumo reconciliado com os dados principais da fatura para o mes atual."
            )

    def _extract_labeled_reference_month(self, lines: list[str], normalized_lines: list[str]) -> str | None:
        for line, normalized in zip(lines, normalized_lines, strict=False):
            if any(label in normalized for label in self.REFERENCE_LABELS):
                month = parse_reference_month(line)
                if month:
                    return month
        return None

    def _extract_labeled_total_value(self, lines: list[str], normalized_lines: list[str]) -> Decimal | None:
        for line, normalized in zip(lines, normalized_lines, strict=False):
            if not any(label in normalized for label in self.TOTAL_LABELS):
                continue
            values = self._extract_money_values(line)
            if values:
                return values[-1]
        return None

    def _extract_money_values(self, line: str) -> list[Decimal]:
        matches = re.findall(r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+[.,]\d{2})", line)
        values = [parse_decimal(match) for match in matches]
        return [value for value in values if value is not None and Decimal("1") <= value <= Decimal("50000")]

    def _extract_tariff_flag(self, lines: list[str], normalized_lines: list[str]) -> str | None:
        for line, normalized in zip(lines, normalized_lines, strict=False):
            if "bandeira" not in normalized and "tarifaria" not in normalized:
                continue
            for marker, label in self.TARIFF_FLAGS:
                if marker in normalized:
                    return label

        normalized_text = " ".join(normalized_lines)
        for marker, label in self.TARIFF_FLAGS:
            if marker in normalized_text:
                return label
        return None

    def _previous_month(self, value: date) -> str:
        year = value.year
        month = value.month - 1
        if month == 0:
            year -= 1
            month = 12
        return f"{year:04d}-{month:02d}"
