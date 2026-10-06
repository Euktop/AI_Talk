"""Нормализация сырых тегов из LLM в Tag.

Правила:
- всё в lowercase;
- убираем ведущий '#' и любые '#' внутри;
- ё → е (совместимость с будущими русскими алиасами);
- подчёркивания и пробелы → дефис;
- схлопываем повторные дефисы и слэши;
- обрезаем краевые дефисы и слэши;
- если тег не проходит валидацию Tag — возвращаем None.
"""

from __future__ import annotations

import re

from tag_summary.domain.value_objects.tag import Tag

_MULTI_DASH_RE = re.compile(r"-{2,}")
_MULTI_SLASH_RE = re.compile(r"/{2,}")


class TagNormalizer:
    """Преобразует произвольную строку в Tag или None, если невозможно."""

    def normalize(self, raw: str) -> Tag | None:
        if raw is None:
            return None
        s = str(raw).strip().lower()
        s = s.replace("#", "")
        s = s.replace("ё", "е")
        s = s.replace("_", "-")
        s = re.sub(r"\s+", "-", s)
        s = _MULTI_DASH_RE.sub("-", s)
        s = _MULTI_SLASH_RE.sub("/", s)
        s = s.strip("-/ ")
        if not s:
            return None
        try:
            return Tag(s)
        except Exception:
            return None
