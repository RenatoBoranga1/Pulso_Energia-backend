from __future__ import annotations

from datetime import date, datetime


def parse_brazilian_date(value: str) -> date | None:
    cleaned = value.strip()
    for pattern in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            parsed = datetime.strptime(cleaned, pattern)
            return parsed.date()
        except ValueError:
            continue
    return None

