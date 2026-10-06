"""Use case: применение утверждённого списка тегов к файлам vault.

Работает как collect: use case режет файлы на чанки по files_per_batch,
параллелит чанки по max_parallel. Adapter упаковывает чанк в один
custom-файл с JSON-запросом, возвращает N JSON-ответов (по одному на файл).

Утверждённый список тегов добавляется в system_prompt чанка — так он
не дублируется 16 раз.

Мягкая валидация: теги вне утверждённого списка отбрасываются с warning.
Per-file изоляция: ошибка одного файла не роняет батч.
Прогресс пишется append_jsonl после каждого файла (resume).
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from tag_summary.application.collect_candidates import (
    ARTIFACT_NAME as COLLECT_ARTIFACT,
    strip_frontmatter,
    truncate_content,
)
from tag_summary.application.context import RunContext
from tag_summary.domain.exceptions import (
    ConfigError,
    FileReadError,
    FileWriteError,
    LLMError,
    LLMFormatError,
)
from tag_summary.domain.ports.i_file_reader import IFileReader
from tag_summary.domain.ports.i_file_writer import IFileWriter
from tag_summary.domain.ports.i_llm_client import ILLMClient
from tag_summary.domain.ports.i_prompt_provider import IPromptProvider
from tag_summary.domain.services.structural_tag_resolver import StructuralTagResolver
from tag_summary.domain.value_objects.tag import Tag, TagSet

logger = logging.getLogger(__name__)

ARTIFACT_NAME = "05_applied"
FINAL_TAGS_ARTIFACT = "04_final_tags"
MAX_TAGS_PER_FILE = 5

_FATAL_EXCEPTIONS = (LLMError, FileReadError, FileWriteError)


def _compose_body(content: str) -> str:
    return truncate_content(strip_frontmatter(content))


def _compose_apply_instruction(
    instruction: str,
    approved_json: str,
    n: int,
) -> str:
    """Инструкция для пакетного режима apply."""
    return (
        f"{instruction}\n\n"
        "## УТВЕРЖДЁННЫЙ СПИСОК ТЕГОВ\n\n"
        f"{approved_json}\n\n"
        "Используй ТОЛЬКО теги из этого списка. Любой тег вне списка — "
        "игнорируется.\n\n"
        f"## ПАКЕТНЫЙ РЕЖИМ: {n} ФАЙЛОВ\n\n"
        "Входные данные — JSON-объект с полем `files`: массив из N элементов, "
        "у каждого есть `idx` (1..N) и `content` (текст файла без frontmatter).\n"
        "Для каждого файла выбери до 5 тегов из утверждённого списка.\n\n"
        "ФОРМАТ ОТВЕТА:\n"
        "{\"responses\": [[\"тег1\", \"тег2\"], [\"тег3\", \"тег4\"], ...]}\n"
        f"Длина массива `responses` должна быть ровно {n}. Порядок — "
        "по возрастанию `idx` из входных данных.\n"
        "Никакого текста до или после JSON."
    )


class ApplyFinalTagsUseCase:
    """Применяет утверждённые теги к каждому файлу vault."""

    def __init__(
        self,
        *,
        reader: IFileReader,
        writer: IFileWriter,
        llm: ILLMClient,
        prompts: IPromptProvider,
        resolver: StructuralTagResolver | None = None,
        files_per_batch: int = 16,
        max_parallel: int = 8,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._llm = llm
        self._prompts = prompts
        self._resolver = resolver or StructuralTagResolver()
        self._files_per_batch = max(1, files_per_batch)
        self._max_parallel = max(1, max_parallel)

    def execute(
        self,
        ctx: RunContext,
        *,
        limit: int | None = None,
    ) -> int:
        ctx.mark_started("apply")

        if not ctx.cache_store.exists(FINAL_TAGS_ARTIFACT):
            ctx.mark_failed(
                "apply",
                f"{FINAL_TAGS_ARTIFACT}.json not found. Run 'approve' first.",
            )
            raise ConfigError(
                "Approved tag list not found. Run 'tag_summary approve' first."
            )

        final_data = ctx.cache_store.read_json(FINAL_TAGS_ARTIFACT)
        approved_tags: list[str] = final_data.get("approved_tags") or []
        if not approved_tags:
            ctx.mark_failed("apply", "approved_tags list is empty")
            raise ConfigError("Approved tag list is empty. Nothing to apply.")

        approved_set = set(approved_tags)
        approved_json = json.dumps(sorted(approved_set), ensure_ascii=False)
        instruction = self._prompts.get_apply_prompt()

        candidates_rows = ctx.cache_store.read_jsonl(COLLECT_ARTIFACT)

        processed: set[str] = set()
        if ctx.cache_store.exists(ARTIFACT_NAME):
            try:
                existing = ctx.cache_store.read_jsonl(ARTIFACT_NAME)
                processed = {
                    str(r.get("path")) for r in existing if r.get("path")
                }
                logger.info(
                    "Apply: resuming, %d files already processed",
                    len(processed),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Apply: cannot read existing JSONL: %s", exc
                )
                processed = set()

        # Отбираем pending. Файлы без frontmatter помечаем skip сразу.
        pending: list[dict[str, Any]] = []
        skipped = 0
        for row in candidates_rows:
            rel_path = str(row.get("path") or "")
            if not rel_path or rel_path in processed:
                continue
            if not row.get("has_frontmatter"):
                logger.info("Apply: skipping %s (no frontmatter)", rel_path)
                ctx.cache_store.append_jsonl(ARTIFACT_NAME, {
                    "path": rel_path, "status": "skipped",
                    "reason": "no_frontmatter", "tags": [],
                })
                skipped += 1
                continue
            pending.append(row)

        if limit is not None and limit > 0:
            logger.info(
                "Apply: limit=%d — processing only first %d files",
                limit, limit,
            )
            pending = pending[:limit]

        counters = {"applied": 0, "skipped": skipped, "failed": 0}

        if not pending:
            logger.info("Apply: nothing to process")
            ctx.mark_done(
                "apply",
                applied=0, skipped=skipped, failed=0,
            )
            return 0

        batch_mode = (
            getattr(self._llm, "supports_batch", False)
            and self._files_per_batch > 1
        )

        if batch_mode:
            self._execute_batched(
                ctx, pending, approved_set, approved_json,
                instruction, counters,
            )
        else:
            self._execute_sequential(
                ctx, pending, approved_set, approved_json,
                instruction, counters,
            )

        ctx.mark_done(
            "apply",
            applied=counters["applied"],
            skipped=counters["skipped"],
            failed=counters["failed"],
        )
        logger.info(
            "Apply done: applied=%d, skipped=%d, failed=%d",
            counters["applied"], counters["skipped"], counters["failed"],
        )
        return counters["applied"]

    def _execute_batched(
        self,
        ctx: RunContext,
        pending: list[dict[str, Any]],
        approved_set: set[str],
        approved_json: str,
        instruction: str,
        counters: dict[str, int],
    ) -> None:
        chunk_size = self._files_per_batch
        chunks = [
            pending[i:i + chunk_size]
            for i in range(0, len(pending), chunk_size)
        ]
        logger.info(
            "Apply: %d files in %d chunk(s) of %d, waves of %d",
            len(pending), len(chunks), chunk_size, self._max_parallel,
        )

        # Предварительно прочитаем все файлы (нужно для compose_body).
        vfs: dict[str, Any] = {}
        for row in pending:
            rel_path = str(row.get("path"))
            vfs[rel_path] = self._reader.read(rel_path)

        def process_chunk(chunk: list[dict[str, Any]]) -> list[str]:
            chunk_instruction = _compose_apply_instruction(
                instruction, approved_json, len(chunk)
            )
            user_prompts = [
                _compose_body(vfs[str(r.get("path"))].content)
                for r in chunk
            ]
            return self._llm.ask_json_batch(
                system_prompt=chunk_instruction,
                user_prompts=user_prompts,
                model="smart",
            )

        results_by_chunk: list[list[str]] = [[] for _ in chunks]
        with ThreadPoolExecutor(max_workers=self._max_parallel) as pool:
            futures = {
                pool.submit(process_chunk, c): i
                for i, c in enumerate(chunks)
            }
            for fut in futures:
                idx = futures[fut]
                try:
                    results_by_chunk[idx] = fut.result()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Apply chunk %d failed", idx + 1)
                    ctx.mark_failed(
                        "apply", f"chunk {idx + 1}: {exc}"
                    )
                    raise

        for i, chunk in enumerate(chunks):
            responses = results_by_chunk[i]
            if len(responses) != len(chunk):
                logger.warning(
                    "Apply chunk %d: expected %d responses, got %d — "
                    "marking whole chunk as failed",
                    i + 1, len(chunk), len(responses),
                )
                for row in chunk:
                    rel_path = str(row.get("path"))
                    ctx.cache_store.append_jsonl(ARTIFACT_NAME, {
                        "path": rel_path, "status": "failed",
                        "reason": "wrong response count", "tags": [],
                    })
                    counters["failed"] += 1
                continue

            for row, raw in zip(chunk, responses):
                rel_path = str(row.get("path"))
                try:
                    chosen_raw = self._parse_choice(raw)
                    tags = self._assemble_tags(
                        rel_path, chosen_raw, approved_set
                    )
                    self._writer.set_tags(rel_path, tags)
                    ctx.cache_store.append_jsonl(ARTIFACT_NAME, {
                        "path": rel_path, "status": "applied",
                        "tags": [t.value for t in tags],
                    })
                    counters["applied"] += 1
                except FileWriteError:
                    logger.exception(
                        "Apply: fatal write error on %s", rel_path
                    )
                    ctx.mark_failed(
                        "apply", f"{rel_path}: write fatal"
                    )
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Apply: %s — failed: %s", rel_path, exc
                    )
                    ctx.cache_store.append_jsonl(ARTIFACT_NAME, {
                        "path": rel_path, "status": "failed",
                        "reason": f"{type(exc).__name__}: {exc}",
                        "tags": [],
                    })
                    counters["failed"] += 1

            logger.info(
                "Apply chunk %d/%d done (applied total=%d, failed total=%d)",
                i + 1, len(chunks),
                counters["applied"], counters["failed"],
            )

    def _execute_sequential(
        self,
        ctx: RunContext,
        pending: list[dict[str, Any]],
        approved_set: set[str],
        approved_json: str,
        instruction: str,
        counters: dict[str, int],
    ) -> None:
        for idx, row in enumerate(pending, start=1):
            rel_path = str(row.get("path"))
            try:
                vf = self._reader.read(rel_path)
                user_prompt = (
                    f"=== ФИНАЛЬНЫЙ СПИСОК ТЕГОВ ===\n\n{approved_json}\n\n"
                    f"=== СОДЕРЖИМОЕ ФАЙЛА ===\n\n{_compose_body(vf.content)}\n"
                    f"=== КОНЕЦ ==="
                )
                raw = self._llm.ask_json(
                    system_prompt=instruction,
                    user_prompt=user_prompt,
                    model="smart",
                )
                chosen_raw = self._parse_choice(raw)
                tags = self._assemble_tags(
                    rel_path, chosen_raw, approved_set
                )
                self._writer.set_tags(rel_path, tags)
                ctx.cache_store.append_jsonl(ARTIFACT_NAME, {
                    "path": rel_path, "status": "applied",
                    "tags": [t.value for t in tags],
                })
                counters["applied"] += 1
            except _FATAL_EXCEPTIONS:
                logger.exception("Apply: fatal on %s", rel_path)
                ctx.mark_failed("apply", f"{rel_path}: fatal")
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Apply: %s — failed: %s", rel_path, exc
                )
                ctx.cache_store.append_jsonl(ARTIFACT_NAME, {
                    "path": rel_path, "status": "failed",
                    "reason": f"{type(exc).__name__}: {exc}",
                    "tags": [],
                })
                counters["failed"] += 1
            if idx % 10 == 0:
                logger.info(
                    "Apply progress: %d/%d (applied=%d, failed=%d)",
                    idx, len(pending),
                    counters["applied"], counters["failed"],
                )

    def _assemble_tags(
        self,
        rel_path: str,
        chosen_raw: list[str],
        approved_set: set[str],
    ) -> tuple[Tag, ...]:
        known: list[str] = []
        unknown: list[str] = []
        for c in chosen_raw:
            if c in approved_set:
                known.append(c)
            else:
                unknown.append(c)
        if unknown:
            logger.warning(
                "Apply: %s — ignoring %d tag(s) outside approved list: %s",
                rel_path, len(unknown), unknown,
            )
        structural = self._resolver.resolve(rel_path)
        structural_values = {t.value for t in structural}
        filtered = [c for c in known if c not in structural_values]
        combined: list[Tag] = list(structural)
        seen = {t.value for t in combined}
        for raw_tag in filtered:
            if raw_tag in seen:
                continue
            seen.add(raw_tag)
            combined.append(Tag(raw_tag))
            if len(combined) >= MAX_TAGS_PER_FILE:
                break
        tag_set = TagSet(tags=tuple(combined), max_size=MAX_TAGS_PER_FILE)
        return tuple(tag_set)

    @staticmethod
    def _parse_choice(raw: str) -> list[str]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMFormatError(f"apply: invalid JSON: {exc}") from exc

        if isinstance(parsed, dict):
            extracted = None
            for key in ("tags", "selected", "result", "items"):
                inner = parsed.get(key)
                if isinstance(inner, list):
                    extracted = inner
                    break
            if extracted is None and len(parsed) == 1:
                only = next(iter(parsed.values()))
                if isinstance(only, list):
                    extracted = only
            if extracted is None:
                keys = list(parsed.keys())
                if keys and all(
                    isinstance(k, str) and k.strip() for k in keys
                ):
                    logger.warning(
                        "apply: accepting dict with tags as keys: %s",
                        keys[:5],
                    )
                    extracted = keys
                else:
                    raise LLMFormatError(
                        f"apply: dict without array value, keys={keys}"
                    )
            parsed = extracted

        if not isinstance(parsed, list):
            raise LLMFormatError(
                f"apply: expected JSON array, got {type(parsed).__name__}"
            )

        result: list[str] = []
        for item in parsed:
            if isinstance(item, str):
                result.append(item.strip())
            else:
                raise LLMFormatError(
                    f"apply: array item is not a string: {item!r}"
                )
        return result
