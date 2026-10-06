"""Use case: сбор тегов-кандидатов для каждого файла vault.

Параллельность и батчинг — на стороне use case:
- Файлы режутся на чанки по files_per_batch (для custom это 16).
- Чанки идут волнами по max_parallel (для custom это 8).
- Каждый чанк получает свой instruction с правильным N.
- Один чанк = один вызов LLM = один custom-файл с N запросами.

Для backend'ов без batch (local/web) всё идёт как есть: adapter
сам параллелит одиночные запросы внутри своего пула.
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from tag_summary.application.context import RunContext
from tag_summary.domain.exceptions import LLMFormatError
from tag_summary.domain.ports.i_file_reader import IFileReader
from tag_summary.domain.ports.i_llm_client import ILLMClient
from tag_summary.domain.ports.i_prompt_provider import IPromptProvider
from tag_summary.domain.services.tag_normalizer import TagNormalizer

logger = logging.getLogger(__name__)

ARTIFACT_NAME = "01_candidates"
MIN_EXPECTED_TAG_COUNT = 5

MAX_CONTENT_CHARS = 6000
HEAD_CHARS = 4000
TAIL_CHARS = 1000

DEFAULT_EXCLUDE_DIRS: tuple[str, ...] = (
    ".git", ".obsidian", ".smart-env", ".trash", ".ai_cache",
    "00 Входящие", "99 Вложения", "AI_Reports",
)

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def strip_frontmatter(content: str) -> str:
    if not content.startswith("---"):
        return content
    end = content.find("\n---", 3)
    if end == -1:
        return content
    body_start = content.find("\n", end + 4)
    if body_start == -1:
        return ""
    return content[body_start + 1:].lstrip("\n")


def truncate_content(content: str, limit: int = MAX_CONTENT_CHARS) -> str:
    if len(content) <= limit:
        return content
    head = content[:HEAD_CHARS]
    tail = content[-TAIL_CHARS:]
    middle_start = HEAD_CHARS
    middle_end = len(content) - TAIL_CHARS
    if middle_end <= middle_start:
        return content[:limit]
    middle = content[middle_start:middle_end]
    headings: list[str] = []
    for m in _HEADING_RE.finditer(middle):
        line = f"{m.group(1)} {m.group(2).strip()}"
        if line not in headings:
            headings.append(line)
    omitted = len(middle)
    parts = [head.rstrip()]
    parts.append(
        f"\n\n[... опущено {omitted} символов, ниже список заголовков из середины ...]\n"
    )
    parts.append("\n".join(headings) if headings else "(середина без заголовков)")
    parts.append("\n[... конец опущенного фрагмента ...]\n\n")
    parts.append(tail.lstrip())
    return "".join(parts)


def _compose_body(content: str) -> str:
    return truncate_content(strip_frontmatter(content))


def _compose_batch_instruction(instruction: str, n: int) -> str:
    """Инструкция для пакетного режима с фиксированным N."""
    return (
        f"{instruction}\n\n"
        f"## ПАКЕТНЫЙ РЕЖИМ: {n} ФАЙЛОВ\n\n"
        "Входные данные — JSON-объект с полем `files`: массив из N элементов, "
        "у каждого есть `idx` (1..N) и `content` (текст файла).\n"
        "Для каждого файла сгенерируй 5–10 тегов по правилам выше.\n\n"
        "ФОРМАТ ОТВЕТА:\n"
        "{\"responses\": [[\"тег1\", \"тег2\"], [\"тег3\", \"тег4\"], ...]}\n"
        f"Длина массива `responses` должна быть ровно {n}. Порядок — "
        "по возрастанию `idx` из входных данных.\n"
        "Никакого текста до или после JSON."
    )


class CollectCandidatesUseCase:
    """Собирает теги-кандидаты для всех .md файлов vault."""

    def __init__(
        self,
        *,
        reader: IFileReader,
        llm: ILLMClient,
        prompts: IPromptProvider,
        normalizer: TagNormalizer | None = None,
        files_per_batch: int = 16,
        max_parallel: int = 8,
    ) -> None:
        self._reader = reader
        self._llm = llm
        self._prompts = prompts
        self._normalizer = normalizer or TagNormalizer()
        self._files_per_batch = max(1, files_per_batch)
        self._max_parallel = max(1, max_parallel)

    def execute(
        self,
        ctx: RunContext,
        *,
        exclude_dirs: tuple[str, ...] = DEFAULT_EXCLUDE_DIRS,
    ) -> int:
        ctx.mark_started("collect")
        rel_paths = self._reader.list_markdown_files(exclude_dirs=exclude_dirs)
        logger.info("Collect: %d markdown files in vault", len(rel_paths))

        processed: set[str] = set()
        if ctx.cache_store.exists(ARTIFACT_NAME):
            try:
                existing = ctx.cache_store.read_jsonl(ARTIFACT_NAME)
                processed = {
                    str(r.get("path")) for r in existing if r.get("path")
                }
                logger.info(
                    "Collect: resuming, %d files already processed",
                    len(processed),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Collect: cannot read existing JSONL: %s", exc
                )
                processed = set()

        pending = [p for p in rel_paths if p not in processed]
        logger.info("Collect: %d files to process", len(pending))

        if not pending:
            total = len(processed)
            ctx.mark_done("collect", files_processed=total)
            return total

        instruction = self._prompts.get_collect_prompt()

        vfs: dict[str, Any] = {}
        for rel_path in pending:
            vfs[rel_path] = self._reader.read(rel_path)

        batch_mode = (
            getattr(self._llm, "supports_batch", False)
            and self._files_per_batch > 1
        )

        if batch_mode:
            raw_responses = self._collect_batched(
                ctx, pending, vfs, instruction
            )
        else:
            raw_responses = self._collect_plain(
                ctx, pending, vfs, instruction
            )

        if len(raw_responses) != len(pending):
            raise LLMFormatError(
                f"Collect: expected {len(pending)} responses, "
                f"got {len(raw_responses)}"
            )

        for rel_path, raw in zip(pending, raw_responses):
            candidates = self._parse_candidates(raw)
            vf = vfs[rel_path]
            row = {
                "path": rel_path,
                "candidates": self._normalize_candidates(candidates),
                "existing_tags": list(vf.tags),
                "has_frontmatter": vf.has_frontmatter,
            }
            ctx.cache_store.append_jsonl(ARTIFACT_NAME, row)

        total = len(processed) + len(pending)
        ctx.mark_done("collect", files_processed=total)
        logger.info("Collect done: %d files total", total)
        return total

    def _collect_batched(
        self,
        ctx: RunContext,
        pending: list[str],
        vfs: dict[str, Any],
        instruction: str,
    ) -> list[str]:
        chunk_size = self._files_per_batch
        chunks = [
            pending[i:i + chunk_size]
            for i in range(0, len(pending), chunk_size)
        ]
        logger.info(
            "Collect: %d files in %d chunk(s) of %d, waves of %d",
            len(pending), len(chunks), chunk_size, self._max_parallel,
        )

        def process_chunk(chunk: list[str]) -> list[str]:
            batch_instruction = _compose_batch_instruction(
                instruction, len(chunk)
            )
            user_prompts = [
                _compose_body(vfs[p].content) for p in chunk
            ]
            return self._llm.ask_json_batch(
                system_prompt=batch_instruction,
                user_prompts=user_prompts,
                model="smart",
            )

        results_by_chunk: list[list[str]] = [[] for _ in chunks]
        with ThreadPoolExecutor(max_workers=self._max_parallel) as pool:
            futures = {
                pool.submit(process_chunk, c): i
                for i, c in enumerate(chunks)
            }
            for fut, idx in [(f, futures[f]) for f in futures]:
                try:
                    results_by_chunk[idx] = fut.result()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Collect chunk %d failed", idx + 1)
                    ctx.mark_failed(
                        "collect", f"chunk {idx + 1}: {exc}"
                    )
                    raise

        flat: list[str] = []
        for i, chunk in enumerate(chunks):
            if len(results_by_chunk[i]) != len(chunk):
                raise LLMFormatError(
                    f"Collect chunk {i + 1}: expected {len(chunk)} "
                    f"responses, got {len(results_by_chunk[i])}"
                )
            flat.extend(results_by_chunk[i])
        return flat

    def _collect_plain(
        self,
        ctx: RunContext,
        pending: list[str],
        vfs: dict[str, Any],
        instruction: str,
    ) -> list[str]:
        logger.info(
            "Collect: sending %d prompts to LLM (backend=%s)",
            len(pending), getattr(self._llm, "backend", "?"),
        )
        user_prompts = [_compose_body(vfs[p].content) for p in pending]
        try:
            return self._llm.ask_json_batch(
                system_prompt=instruction,
                user_prompts=user_prompts,
                model="smart",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Collect batch failed")
            ctx.mark_failed("collect", f"batch: {exc}")
            raise

    @staticmethod
    def _parse_candidates(raw: str) -> list[str]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMFormatError(f"collect: invalid JSON: {exc}") from exc

        if isinstance(parsed, dict):
            extracted = None
            for key in ("tags", "candidates", "result", "items", "data"):
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
                    extracted = keys
                else:
                    raise LLMFormatError(
                        f"collect: dict without array value, keys={keys}"
                    )
            parsed = extracted

        if not isinstance(parsed, list):
            raise LLMFormatError(
                f"collect: expected JSON array, got {type(parsed).__name__}"
            )

        result: list[str] = []
        for item in parsed:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict) and "tag" in item:
                result.append(str(item["tag"]))
            else:
                raise LLMFormatError(
                    f"collect: array item is not a string or {{tag}}: {item!r}"
                )
        if len(result) < MIN_EXPECTED_TAG_COUNT:
            logger.warning(
                "collect: got %d tags (< %d expected)",
                len(result), MIN_EXPECTED_TAG_COUNT,
            )
        return result

    def _normalize_candidates(self, raw_tags: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for raw in raw_tags:
            tag = self._normalizer.normalize(raw)
            if tag is None:
                continue
            if tag.value in seen:
                continue
            seen.add(tag.value)
            result.append(tag.value)
        return result
