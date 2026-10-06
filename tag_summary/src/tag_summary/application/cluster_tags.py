"""Use case: семантическая кластеризация тегов через LLM.

Инструкция → system_prompt, JSON-словарь тегов → user_prompt.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from tag_summary.application.aggregate_frequencies import ARTIFACT_NAME as FREQ_ARTIFACT
from tag_summary.application.context import RunContext
from tag_summary.domain.exceptions import CacheError, LLMFormatError, ValidationError
from tag_summary.domain.ports.i_llm_client import ILLMClient
from tag_summary.domain.ports.i_prompt_provider import IPromptProvider
from tag_summary.domain.value_objects.tag import Tag
from tag_summary.domain.value_objects.tag_cluster import TagCluster

logger = logging.getLogger(__name__)

ARTIFACT_NAME = "03_clusters"
DEFAULT_BATCH_SIZE = 300


def _compose_user_message(data: str) -> str:
    return (
        f"=== СПИСОК ТЕГОВ С ЧАСТОТАМИ ===\n\n"
        f"{data}\n"
        f"=== КОНЕЦ СПИСКА ==="
    )


class ClusterTagsUseCase:
    """Группирует теги-синонимы в кластеры с каноническим тегом."""

    def __init__(
        self,
        *,
        llm: ILLMClient,
        prompts: IPromptProvider,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._llm = llm
        self._prompts = prompts
        self._batch_size = batch_size

    def execute(self, ctx: RunContext) -> dict[str, Any]:
        ctx.mark_started("cluster")

        try:
            freq_data = ctx.cache_store.read_json(FREQ_ARTIFACT)
        except CacheError as exc:
            ctx.mark_failed("cluster", str(exc))
            raise

        filtered = freq_data.get("filtered") or {}
        if not filtered:
            logger.warning("Cluster: filtered tag list is empty")
            result = {
                "batch_size": self._batch_size,
                "total_input": 0,
                "total_clusters": 0,
                "clusters": [],
            }
            ctx.cache_store.write_json(ARTIFACT_NAME, result)
            ctx.mark_done("cluster", total_clusters=0)
            return result

        instruction = self._prompts.get_cluster_prompt()
        sorted_items = sorted(filtered.items(), key=lambda kv: (-kv[1], kv[0]))
        batches = _chunk(sorted_items, self._batch_size)
        logger.info(
            "Cluster: %d tags in %d batch(es) of size %d",
            len(sorted_items), len(batches), self._batch_size,
        )

        merged: dict[str, set[str]] = {}
        for idx, batch in enumerate(batches, start=1):
            batch_map = dict(batch)
            batch_json = json.dumps(batch_map, ensure_ascii=False, indent=2)
            user_prompt = _compose_user_message(batch_json)
            try:
                raw = self._llm.ask_json(
                    system_prompt=instruction,
                    user_prompt=user_prompt,
                    model="smart",
                )
            except Exception as exc:  # noqa: BLE001
                ctx.mark_failed("cluster", f"batch {idx}/{len(batches)}: {exc}")
                raise

            batch_clusters = self._parse_cluster_response(raw, idx)
            _merge_into(merged, batch_clusters)
            logger.info(
                "Cluster: batch %d/%d produced %d clusters, merged total = %d",
                idx, len(batches), len(batch_clusters), len(merged),
            )

        _resolve_conflicts(merged)
        _ensure_coverage(merged, set(filtered.keys()))

        clusters = _build_tag_clusters(merged, filtered)
        clusters.sort(key=lambda c: (-c.total_frequency, c.canonical.value))

        result = {
            "batch_size": self._batch_size,
            "total_input": len(filtered),
            "total_clusters": len(clusters),
            "clusters": [
                {
                    "canonical": c.canonical.value,
                    "aliases": list(c.aliases),
                    "total_frequency": c.total_frequency,
                }
                for c in clusters
            ],
        }
        ctx.cache_store.write_json(ARTIFACT_NAME, result)
        ctx.mark_done(
            "cluster",
            total_input=len(filtered),
            total_clusters=len(clusters),
        )
        return result

    @staticmethod
    def _parse_cluster_response(raw: str, batch_idx: int) -> dict[str, list[str]]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMFormatError(
                f"cluster: batch {batch_idx} invalid JSON: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise LLMFormatError(
                f"cluster: batch {batch_idx} expected JSON object, got "
                f"{type(parsed).__name__}"
            )
        result: dict[str, list[str]] = {}
        for canonical, aliases in parsed.items():
            if not isinstance(canonical, str) or not canonical.strip():
                raise LLMFormatError(
                    f"cluster: batch {batch_idx} non-string canonical: {canonical!r}"
                )
            if aliases is None:
                aliases = []
            if not isinstance(aliases, list):
                raise LLMFormatError(
                    f"cluster: batch {batch_idx} non-list aliases: {aliases!r}"
                )
            result[canonical.strip()] = [str(a) for a in aliases if a]
        return result


def _chunk(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _merge_into(target: dict[str, set[str]], source: dict[str, list[str]]) -> None:
    for canonical, aliases in source.items():
        bucket = target.setdefault(canonical, set())
        for alias in aliases:
            if alias != canonical:
                bucket.add(alias)


def _resolve_conflicts(merged: dict[str, set[str]]) -> None:
    changed = True
    while changed:
        changed = False
        canonicals = list(merged.keys())
        for i, a in enumerate(canonicals):
            if a not in merged:
                continue
            tags_a = {a} | merged[a]
            for b in canonicals[i + 1:]:
                if b not in merged:
                    continue
                tags_b = {b} | merged[b]
                if tags_a & tags_b:
                    merged[a].update(merged[b])
                    merged[a].add(b)
                    del merged[b]
                    changed = True
                    break
            if changed:
                break


def _ensure_coverage(merged: dict[str, set[str]], input_tags: set[str]) -> None:
    covered: set[str] = set()
    for canonical, aliases in merged.items():
        covered.add(canonical)
        covered.update(aliases)
    missing = input_tags - covered
    if missing:
        logger.warning(
            "Cluster: %d input tag(s) missing from LLM output; "
            "adding as self-canonical: %s",
            len(missing), sorted(missing)[:10],
        )
        for tag in missing:
            merged.setdefault(tag, set())


def _build_tag_clusters(
    merged: dict[str, set[str]],
    frequencies: dict[str, int],
) -> list[TagCluster]:
    result: list[TagCluster] = []
    for canonical, aliases in merged.items():
        try:
            canonical_tag = Tag(canonical)
        except ValidationError:
            logger.warning("Cluster: dropping invalid canonical %r", canonical)
            continue
        valid_aliases = sorted(a for a in aliases if a != canonical)
        total = frequencies.get(canonical, 0) + sum(
            frequencies.get(a, 0) for a in valid_aliases
        )
        result.append(
            TagCluster(
                canonical=canonical_tag,
                aliases=tuple(valid_aliases),
                total_frequency=total,
            )
        )
    return result
