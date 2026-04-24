from __future__ import annotations

from app.utils.text import normalize_whitespace


class TextNormalizationService:
    def normalize(self, text: str) -> str:
        return normalize_whitespace(text)

