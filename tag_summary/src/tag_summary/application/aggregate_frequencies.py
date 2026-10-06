"""Use case: подсчёт частоты нормализованных тегов.

Работает без LLM. Читает 01_candidates.jsonl, объединяет кандидатов от
LLM и уже существующие теги файлов, дедуплицирует внутри файла, считает
частоту. Структурные теги (project, moc, daily, resource, system, archive
и т.д.) исключаются — они проставляются автоматически по пути файла
и не должны участвовать в семантическом анализе.

Порог: теги с частотой ≤ threshold отбрасываются (по умолчанию 3).
Итог: 02_frequency.json с полным и отфильтрованным словарями.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from tag_summary.application.context import RunContext
from tag_summary.application.collect_candidates import ARTIFACT_NAME as COLLECT_ARTIFACT
from tag_summary.domain.exceptions import CacheError
from tag_summary.domain.services.structural_tag_resolver import StructuralTagResolver
from tag_summary.domain.services.tag_normalizer import TagNormalizer
from tag_summary.domain.value_objects.tag import Tag

logger = logging.getLogger(__name__)

ARTIFACT_NAME = "02_frequency"
DEFAULT_THRESHOLD = 3


class AggregateFrequenciesUseCase:
    """Считает частоты тегов по всем файлам vault."""

    def __init__(
        self,
        *,
        threshold: int = DEFAULT_THRESHOLD,
        normalizer: TagNormalizer | None = None,
        resolver: StructuralTagResolver | None = None,
    ) -> None:
        self._threshold = threshold
        self._normalizer = normalizer or TagNormalizer()
        self._resolver = resolver or StructuralTagResolver()

    def execute(self, ctx: RunContext) -> dict[str, Any]:
        ctx.mark_started("aggregate")

        try:
            rows = ctx.cache_store.read_jsonl(COLLECT_ARTIFACT)
        except CacheError as exc:
            ctx.mark_failed("aggregate", str(exc))
            raise

        counts: Counter[str] = Counter()
        for row in rows:
            self._count_file(row, counts)

        all_map = dict(counts.most_common())
        filtered_map = {k: v for k, v in all_map.items() if v > self._threshold}

        result = {
            "threshold": self._threshold,
            "total_unique_tags": len(all_map),
            "filtered_count": len(filtered_map),
            "all": all_map,
            "filtered": filtered_map,
        }
        ctx.cache_store.write_json(ARTIFACT_NAME, result)
        ctx.mark_done(
            "aggregate",
            total_unique_tags=len(all_map),
            filtered_count=len(filtered_map),
        )
        logger.info(
            "Aggregate: %d unique tags, %d kept after threshold > %d",
            len(all_map), len(filtered_map), self._threshold,
        )
        return result

    def _count_file(self, row: dict[str, Any], counts: Counter[str]) -> None:
        rel_path = str(row.get("path") or "")
        if not rel_path:
            logger.warning("Skipping row without path: %r", row)
            return

        structural = {t.value for t in self._resolver.resolve(rel_path)}
        seen_in_file: set[str] = set()

        for raw in row.get("existing_tags") or []:
            tag = self._normalizer.normalize(str(raw))
            if tag is not None:
                seen_in_file.add(tag.value)

        for raw in row.get("candidates") or []:
            tag = self._normalizer.normalize(str(raw))
            if tag is not None:
                seen_in_file.add(tag.value)

        for value in seen_in_file:
            if value in structural:
                continue
            counts[value] += 1


def ensure_valid_tags(d: dict[str, int]) -> dict[str, int]:
    """Отбрасывает ключи, не проходящие валидацию Tag. Вспомогательная функция."""
    result: dict[str, int] = {}
    for k, v in d.items():
        try:
            Tag(k)
        except Exception:  # noqa: BLE001
            continue
        result[k] = v
    return result
