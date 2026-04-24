from __future__ import annotations

from datetime import date

import pandas as pd


def month_to_timestamp(reference_month: str) -> pd.Timestamp:
    return pd.Timestamp(f"{reference_month}-01")


def timestamp_to_reference_month(value: pd.Timestamp) -> str:
    return value.strftime("%Y-%m")


def add_months(reference_month: str, months: int) -> str:
    timestamp = month_to_timestamp(reference_month) + pd.DateOffset(months=months)
    return timestamp_to_reference_month(timestamp)


def month_name(reference_month: str) -> str:
    timestamp = month_to_timestamp(reference_month)
    return timestamp.strftime("%B %Y")


def today_reference_month(today: date | None = None) -> str:
    current = today or date.today()
    return f"{current.year:04d}-{current.month:02d}"

