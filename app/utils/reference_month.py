from __future__ import annotations

import re

from app.utils.text import normalize_for_matching


MONTH_MAP = {
    "jan": "01",
    "janeiro": "01",
    "fev": "02",
    "fevereiro": "02",
    "mar": "03",
    "marco": "03",
    "abril": "04",
    "abr": "04",
    "mai": "05",
    "maio": "05",
    "jun": "06",
    "junho": "06",
    "jul": "07",
    "julho": "07",
    "ago": "08",
    "agosto": "08",
    "set": "09",
    "setembro": "09",
    "out": "10",
    "outubro": "10",
    "nov": "11",
    "novembro": "11",
    "dez": "12",
    "dezembro": "12",
}


def parse_reference_month(value: str) -> str | None:
    cleaned = normalize_for_matching(value).replace(" ", "")

    match = re.search(r"(?P<year>20\d{2})[-/](?P<month>0[1-9]|1[0-2])", cleaned)
    if match:
        return f"{match.group('year')}-{match.group('month')}"

    match = re.search(r"(?P<month>0?[1-9]|1[0-2])[-/](?P<year>20\d{2})", cleaned)
    if match:
        month = match.group("month").zfill(2)
        return f"{match.group('year')}-{month}"

    match = re.search(r"(?P<label>[a-zç]+)[-/]?(?P<year>20\d{2})", cleaned)
    if match:
        month = MONTH_MAP.get(match.group("label"))
        if month:
            return f"{match.group('year')}-{month}"

    return None

