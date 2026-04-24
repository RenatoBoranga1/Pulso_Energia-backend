from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from app.services.extraction.types import ParsedBillResult, ParsedField, ParsedHistoryEntry
from app.utils.datetime import parse_brazilian_date
from app.utils.numbers import parse_decimal
from app.utils.reference_month import MONTH_MAP, parse_reference_month
from app.utils.text import clean_line_tokens, normalize_for_matching


class BillSemanticParser:
    PROVIDER_CANDIDATES = (
        "enel",
        "cpfl",
        "neoenergia",
        "equatorial",
        "cemig",
        "light",
        "celesc",
        "energisa",
        "rge",
        "edp",
        "copel",
        "coelba",
        "elektro",
    )

    def parse(self, text: str) -> ParsedBillResult:
        lines = clean_line_tokens(text.splitlines())
        normalized_lines = [normalize_for_matching(line) for line in lines]
        result = ParsedBillResult()

        result.concessionaria = self._parse_concessionaria(lines, normalized_lines)
        result.mes_referencia = self._parse_reference_month(lines, normalized_lines)
        result.consumo_kwh = self._parse_consumption(lines, normalized_lines)
        result.dias_faturados = self._parse_days(lines, normalized_lines)
        result.valor_total = self._parse_total_value(lines, normalized_lines)
        result.bandeira_tarifaria = self._parse_tariff_flag(lines, normalized_lines)
        result.unidade_consumidora = self._parse_consumer_unit(lines, normalized_lines)
        result.vencimento = self._parse_due_date(lines, normalized_lines)
        history, history_confidence = self._parse_history(lines, normalized_lines)
        result.historico_consumo = history
        result.historico_consumo_confidence = history_confidence

        if not text.strip():
            result.warnings.append("Nao foi possivel extrair texto legivel do documento.")

        if not any(
            [
                result.concessionaria.value,
                result.mes_referencia.value,
                result.consumo_kwh.value,
                result.valor_total.value,
                result.unidade_consumidora.value,
                result.historico_consumo,
            ]
        ):
            result.warnings.append("Nao foi possivel identificar com seguranca os principais campos da conta.")

        return result

    def _parse_concessionaria(self, lines: list[str], normalized_lines: list[str]) -> ParsedField:
        for original, normalized in zip(lines, normalized_lines, strict=False):
            if "concessionaria" in normalized or "distribuidora" in normalized:
                candidate = original.split(":")[-1].strip()
                if candidate:
                    return ParsedField(candidate, 0.95, original)
            for provider in self.PROVIDER_CANDIDATES:
                if provider in normalized:
                    return ParsedField(original.strip(), 0.85, original)
        return ParsedField(None, 0.0)

    def _parse_reference_month(self, lines: list[str], normalized_lines: list[str]) -> ParsedField:
        for original, normalized in zip(lines, normalized_lines, strict=False):
            if any(label in normalized for label in ("mes de referencia", "referencia", "competencia", "referente a")):
                month = parse_reference_month(original)
                if month:
                    return ParsedField(month, 0.95, original)
        for original in lines:
            month = parse_reference_month(original)
            if month:
                return ParsedField(month, 0.72, original)
        return ParsedField(None, 0.0)

    def _parse_consumption(self, lines: list[str], normalized_lines: list[str]) -> ParsedField:
        labeled_patterns = ("consumo do mes", "consumo", "energia consumida")
        for original, normalized in zip(lines, normalized_lines, strict=False):
            if any(pattern in normalized for pattern in labeled_patterns):
                amount = self._extract_kwh_from_line(original)
                if amount is not None:
                    return ParsedField(amount, 0.93, original)
        for original in lines:
            amount = self._extract_kwh_from_line(original)
            if amount is not None:
                return ParsedField(amount, 0.7, original)
        return ParsedField(None, 0.0)

    def _parse_days(self, lines: list[str], normalized_lines: list[str]) -> ParsedField:
        for original, normalized in zip(lines, normalized_lines, strict=False):
            if "dias faturados" in normalized or "periodo faturado" in normalized:
                days = self._extract_integer_from_line(original)
                if days is not None:
                    return ParsedField(days, 0.92, original)
        for original, normalized in zip(lines, normalized_lines, strict=False):
            if " dias" in normalized:
                days = self._extract_integer_from_line(original)
                if days is not None:
                    return ParsedField(days, 0.65, original)
        return ParsedField(None, 0.0)

    def _parse_total_value(self, lines: list[str], normalized_lines: list[str]) -> ParsedField:
        for original, normalized in zip(lines, normalized_lines, strict=False):
            if any(label in normalized for label in ("total a pagar", "valor total", "valor da fatura", "total")):
                value = self._extract_currency_from_line(original)
                if value is not None:
                    return ParsedField(value, 0.94, original)
        for original in lines:
            value = self._extract_currency_from_line(original)
            if value is not None:
                return ParsedField(value, 0.68, original)
        return ParsedField(None, 0.0)

    def _parse_tariff_flag(self, lines: list[str], normalized_lines: list[str]) -> ParsedField:
        for original, normalized in zip(lines, normalized_lines, strict=False):
            if "bandeira tarifaria" in normalized:
                candidate = original.split(":")[-1].strip()
                if candidate:
                    return ParsedField(candidate, 0.9, original)
        return ParsedField(None, 0.0)

    def _parse_consumer_unit(self, lines: list[str], normalized_lines: list[str]) -> ParsedField:
        for original, normalized in zip(lines, normalized_lines, strict=False):
            if any(label in normalized for label in ("unidade consumidora", "uc ", "uc:")):
                match = re.search(r"(\d{4,})", original)
                if match:
                    return ParsedField(match.group(1), 0.95, original)
                candidate = original.split(":")[-1].strip()
                if candidate:
                    return ParsedField(candidate, 0.78, original)
        return ParsedField(None, 0.0)

    def _parse_due_date(self, lines: list[str], normalized_lines: list[str]) -> ParsedField:
        for original, normalized in zip(lines, normalized_lines, strict=False):
            if "vencimento" in normalized:
                parsed = self._extract_date_from_line(original)
                if parsed:
                    return ParsedField(parsed, 0.94, original)
        for original in lines:
            parsed = self._extract_date_from_line(original)
            if parsed:
                return ParsedField(parsed, 0.6, original)
        return ParsedField(None, 0.0)

    def _parse_history(self, lines: list[str], normalized_lines: list[str]) -> tuple[list[ParsedHistoryEntry], float]:
        anchored_history: list[tuple[int, ParsedHistoryEntry]] = []
        history_section_active = False
        for index, (line, normalized) in enumerate(zip(lines, normalized_lines, strict=False)):
            if "historico" in normalized:
                history_section_active = True
                continue

            entry = self._extract_history_entry(line, normalized, history_section_active)
            if entry is None:
                continue

            if any(item.mes_referencia == entry.mes_referencia for _, item in anchored_history):
                continue

            anchored_history.append((index, entry))
            history_section_active = True

        history: list[ParsedHistoryEntry] = [entry for _, entry in anchored_history]
        for recovered in self._recover_interleaved_history_entries(lines, anchored_history):
            if any(item.mes_referencia == recovered.mes_referencia for item in history):
                continue
            history.append(recovered)

        history.sort(key=lambda item: item.mes_referencia)
        confidence = 0.92 if len(history) >= 10 else 0.9 if len(history) >= 6 else 0.82 if len(history) >= 3 else 0.72 if history else 0.0
        return history, confidence

    def _extract_history_entry(
        self,
        line: str,
        normalized: str,
        history_section_active: bool,
    ) -> ParsedHistoryEntry | None:
        reference_month, month_metadata = self._extract_history_reference_month(line, normalized)
        if reference_month is None:
            return None

        if not history_section_active and not self._looks_like_history_row(normalized):
            return None

        values = [parse_decimal(match) for match in re.findall(r"\d+(?:[.,]\d+)?", line)]
        values = [value for value in values if value is not None and value > 0]
        values = self._strip_history_reference_tokens(values, month_metadata)
        if not values:
            return None

        whole_values = [value for value in values if value == value.to_integral_value()]
        if not whole_values:
            return None

        days: int | None = None
        consumption: Decimal | None = None

        if len(whole_values) >= 2 and 20 <= int(whole_values[-1]) <= 40:
            days = int(whole_values[-1])
            consumption = whole_values[-2]
        elif len(whole_values) == 1:
            consumption = whole_values[0]
        else:
            return None

        if consumption is None or consumption <= 0:
            return None

        return ParsedHistoryEntry(
            mes_referencia=reference_month,
            consumo_kwh=consumption,
            dias_faturados=days,
        )

    def _extract_history_reference_month(
        self,
        line: str,
        normalized: str,
    ) -> tuple[str | None, dict[str, Decimal | str]]:
        stripped = line.strip()
        metadata: dict[str, Decimal | str] = {}

        match = re.match(r"^(?P<year>20\d{2})[-/](?P<month>0[1-9]|1[0-2])\b", stripped)
        if match:
            metadata["year_token"] = Decimal(match.group("year"))
            metadata["month_token"] = Decimal(match.group("month"))
            return f"{match.group('year')}-{match.group('month')}", metadata

        match = re.match(r"^(?P<month>0?[1-9]|1[0-2])[-/](?P<year>20\d{2})\b", stripped)
        if match:
            month = match.group("month").zfill(2)
            metadata["year_token"] = Decimal(match.group("year"))
            metadata["month_token"] = Decimal(month)
            return f"{match.group('year')}-{month}", metadata

        normalized_stripped = normalized.strip()
        match = re.match(r"^(?P<label>[a-z]+)\s+(?P<year>\d{2,4})\b", normalized_stripped)
        if match:
            month = MONTH_MAP.get(match.group("label"))
            if month:
                year_token = match.group("year")
                year = f"20{year_token}" if len(year_token) == 2 else year_token
                metadata["year_suffix_token"] = Decimal(year_token[-2:])
                return f"{year}-{month}", metadata

        return None, metadata

    def _strip_history_reference_tokens(
        self,
        values: list[Decimal],
        metadata: dict[str, Decimal | str],
    ) -> list[Decimal]:
        if not values:
            return values

        stripped = list(values)
        year_token = metadata.get("year_token")
        month_token = metadata.get("month_token")
        year_suffix_token = metadata.get("year_suffix_token")

        if (
            isinstance(year_token, Decimal)
            and isinstance(month_token, Decimal)
            and len(stripped) >= 2
            and (
                (stripped[0] == year_token and stripped[1] == month_token)
                or (stripped[0] == month_token and stripped[1] == year_token)
            )
        ):
            return stripped[2:]

        if isinstance(year_suffix_token, Decimal) and stripped[0] == year_suffix_token:
            return stripped[1:]

        if isinstance(year_token, Decimal) and stripped[0] == year_token:
            return stripped[1:]

        if isinstance(month_token, Decimal) and stripped[0] == month_token:
            return stripped[1:]

        return stripped

    def _looks_like_history_row(self, normalized: str) -> bool:
        return bool(
            re.match(r"^(?:[a-z]{3,9}\s+\d{2,4}|20\d{2}[-/]\d{1,2}|\d{1,2}[-/]20\d{2})\b", normalized)
        )

    def _recover_interleaved_history_entries(
        self,
        lines: list[str],
        anchored_history: list[tuple[int, ParsedHistoryEntry]],
    ) -> list[ParsedHistoryEntry]:
        recovered: list[ParsedHistoryEntry] = []
        for (current_index, current_entry), (next_index, next_entry) in zip(anchored_history, anchored_history[1:], strict=False):
            missing_months = self._missing_descending_months(
                newer_month=current_entry.mes_referencia,
                older_month=next_entry.mes_referencia,
            )
            if len(missing_months) != 2:
                continue
            if len({month[:4] for month in missing_months}) != 1:
                continue

            segment_lines = lines[current_index + 1 : next_index]
            recovered.extend(self._extract_interleaved_gap_entries(segment_lines, missing_months))
        return recovered

    def _extract_interleaved_gap_entries(
        self,
        segment_lines: list[str],
        missing_months: list[str],
    ) -> list[ParsedHistoryEntry]:
        digits = "".join(character for line in segment_lines for character in line if character.isdigit())
        if not digits:
            return []

        year_suffix = missing_months[0][2:4]
        doubled_year_prefix = f"{year_suffix[0]}{year_suffix[0]}{year_suffix[1]}{year_suffix[1]}"
        if digits.startswith(doubled_year_prefix):
            digits = digits[4:]

        if len(digits) > 10:
            digits = digits[-10:]

        if len(digits) != 10:
            return []

        first_row = digits[0::2]
        second_row = digits[1::2]
        entries: list[ParsedHistoryEntry] = []
        for month, compact in zip(missing_months, (first_row, second_row), strict=False):
            if len(compact) != 5:
                return []

            consumo = parse_decimal(compact[:3])
            dias = int(compact[3:])
            if consumo is None or consumo <= 0 or not (20 <= dias <= 40):
                return []

            entries.append(
                ParsedHistoryEntry(
                    mes_referencia=month,
                    consumo_kwh=consumo,
                    dias_faturados=dias,
                )
            )

        return entries

    def _missing_descending_months(self, *, newer_month: str, older_month: str) -> list[str]:
        missing: list[str] = []
        cursor = self._previous_month(newer_month)
        while cursor is not None and cursor != older_month:
            missing.append(cursor)
            if len(missing) > 12:
                return []
            cursor = self._previous_month(cursor)
        return missing if cursor == older_month else []

    def _previous_month(self, value: str) -> str | None:
        if not re.fullmatch(r"20\d{2}-\d{2}", value):
            return None

        year = int(value[:4])
        month = int(value[-2:])
        month -= 1
        if month == 0:
            year -= 1
            month = 12
        return f"{year:04d}-{month:02d}"

    def _extract_kwh_from_line(self, line: str) -> Decimal | None:
        after_unit_candidates: list[Decimal] = []
        for match in re.finditer(r"\bkwh\b", line, re.IGNORECASE):
            segment = line[match.end() : match.end() + 40]
            number_match = re.search(r"[^\d]{0,6}(\d{1,5}(?:[.,]\d{1,4})?)", segment)
            if not number_match:
                continue

            candidate = parse_decimal(number_match.group(1))
            if candidate is not None and candidate > 0:
                after_unit_candidates.append(candidate)

        if after_unit_candidates:
            return max(after_unit_candidates)

        match = re.search(r"(\d{1,5}(?:[.,]\d{1,4})?)\s*kwh\b", line, re.IGNORECASE)
        if match:
            return parse_decimal(match.group(1))
        return None

    def _extract_currency_from_line(self, line: str) -> Decimal | None:
        match = re.search(r"R\$\s*([\d\.,]+)", line, re.IGNORECASE)
        if match:
            return parse_decimal(match.group(1))
        return None

    def _extract_integer_from_line(self, line: str) -> int | None:
        match = re.search(r"(\d{1,3})", line)
        if not match:
            return None
        return int(match.group(1))

    def _extract_date_from_line(self, line: str) -> date | None:
        match = re.search(r"(\d{2}/\d{2}/\d{2,4})", line)
        if not match:
            return None
        return parse_brazilian_date(match.group(1))
