from __future__ import annotations

from decimal import Decimal, InvalidOperation


def parse_decimal(value: str) -> Decimal | None:
    cleaned = (
        value.strip()
        .replace("R$", "")
        .replace("kWh", "")
        .replace("KWH", "")
        .replace(" ", "")
    )
    if not cleaned:
        return None

    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None

