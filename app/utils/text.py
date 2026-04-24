from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


def remove_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_whitespace(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def normalize_for_matching(value: str) -> str:
    normalized = normalize_whitespace(value)
    normalized = remove_accents(normalized).lower()
    return normalized


def clean_line_tokens(lines: Iterable[str]) -> list[str]:
    return [line.strip() for line in lines if line and line.strip()]

