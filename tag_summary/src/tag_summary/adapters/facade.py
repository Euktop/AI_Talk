"""Фасад TagSummary — Python API.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from tag_summary.application.aggregate_frequencies import AggregateFrequenciesUseCase
from tag_summary.application.apply_final_tags import ApplyFinalTagsUseCase
from tag_summary.application.cluster_tags import ClusterTagsUseCase
from tag_summary.application.collect_candidates import CollectCandidatesUseCase
from tag_summary.application.context import RunContext
from tag_summary.application.validate_result import ValidateResultUseCase
from tag_summary.config.settings import Settings, RunDir, load_settings
from tag_summary.infrastructure.cache.jsonl_cache import FileCacheStore
from tag_summary.infrastructure.fs.jason_reader import JasonFileReader
from tag_summary.infrastructure.fs.jason_writer import JasonFileWriter
from tag_summary.infrastructure.jason.runner import JasonRunner
from tag_summary.infrastructure.llm.ai_talk_adapter import AITalkLLMClient
from tag_summary.infrastructure.logging.llm_logger import LLMLogger
from tag_summary.infrastructure.prompt.command_engine_provider import (
    CommandEnginePromptProvider,
)

logger = logging.getLogger(__name__)


class TagSummary:
    """Фасад пайплайна. Один экземпляр на прогон."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        vault_path: str | None = None,
        runs_dir: str | None = None,
        threshold: int | None = None,
        backend: str | None = None,
        parallel: int | None = None,
        files_per_batch: int | None = None,
        config_path: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self._settings = settings or load_settings(
            vault_path=vault_path,
            runs_dir=runs_dir,
            threshold=threshold,
            backend=backend,
            parallel=parallel,
            files_per_batch=files_per_batch,
            config_path=config_path,
        )

        if run_id is None:
            run_path = RunDir.create(self._settings.runs_dir)
            self._run_id = run_path.name
        else:
            run_path = self._settings.runs_dir / run_id
            if not run_path.exists():
                raise FileNotFoundError(f"Run directory not found: {run_path}")
            self._run_id = run_id

        self._run_path = run_path
        self._cache = FileCacheStore(run_path)
        self._llm_logger = LLMLogger(run_path / "logs")
        self._jason = JasonRunner()
        self._reader = JasonFileReader(
            vault_path=self._settings.vault_path,
            runner=self._jason,
        )
        self._writer = JasonFileWriter(
            vault_path=self._settings.vault_path,
            runner=self._jason,
        )
        self._llm = AITalkLLMClient(
            backend=self._settings.llm_backend,
            web_provider=self._settings.web_provider,
            custom_dir=self._settings.custom_dir,
            files_per_batch=self._settings.files_per_batch,
            max_parallel=self._settings.max_parallel,
            llm_logger=self._llm_logger,
        )
        self._prompts = CommandEnginePromptProvider(
            vault_path=self._settings.vault_path,
        )
        self._ctx = RunContext(
            cache_store=self._cache,
            vault_path=self._settings.vault_path,
            run_id=self._run_id,
        )

        logger.info("TagSummary initialised run_id=%s at %s", self._run_id, run_path)

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def run_path(self) -> Path:
        return self._run_path

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def context(self) -> RunContext:
        return self._ctx

    def collect(self) -> int:
        return CollectCandidatesUseCase(
            reader=self._reader,
            llm=self._llm,
            prompts=self._prompts,
            files_per_batch=self._settings.files_per_batch,
            max_parallel=self._settings.max_parallel,
        ).execute(self._ctx)

    def probe(self, rel_path: str) -> dict[str, Any]:
        """Диагностический прогон одного файла. Не пишет в кэш и manifest."""
        use_case = CollectCandidatesUseCase(
            reader=self._reader,
            llm=self._llm,
            prompts=self._prompts,
        )
        result = use_case.probe_one(rel_path)
        self._save_probe_dump(result)
        return result

    def _save_probe_dump(self, result: dict[str, Any]) -> None:
        from datetime import datetime
        import json as _json

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        probe_dir = self._run_path / "logs"
        probe_dir.mkdir(parents=True, exist_ok=True)
        path = probe_dir / f"probe_{ts}.json"
        try:
            with path.open("w", encoding="utf-8") as fh:
                _json.dump(result, fh, ensure_ascii=False, indent=2)
            logger.info("Probe dump saved to %s", path)
        except OSError as exc:
            logger.warning("Failed to save probe dump: %s", exc)

    def aggregate(self) -> dict[str, Any]:
        return AggregateFrequenciesUseCase(
            threshold=self._settings.threshold,
        ).execute(self._ctx)

    def cluster(self) -> dict[str, Any]:
        return ClusterTagsUseCase(
            llm=self._llm,
            prompts=self._prompts,
            batch_size=self._settings.cluster_batch_size,
        ).execute(self._ctx)

    def apply(self, limit: int | None = None) -> int:
        return ApplyFinalTagsUseCase(
            reader=self._reader,
            writer=self._writer,
            llm=self._llm,
            prompts=self._prompts,
            files_per_batch=self._settings.files_per_batch,
            max_parallel=self._settings.max_parallel,
        ).execute(self._ctx, limit=limit)

    def validate(self) -> dict[str, Any]:
        return ValidateResultUseCase(
            validator_script=self._settings.validator_script,
        ).execute(self._ctx)

    def approve(self, approved_tags: list[str]) -> dict[str, Any]:
        from tag_summary.domain.exceptions import ConfigError
        from tag_summary.domain.value_objects.tag import Tag

        if not approved_tags:
            raise ConfigError("approved_tags list is empty")
        clean: list[str] = []
        seen: set[str] = set()
        for raw in approved_tags:
            try:
                tag = Tag(str(raw).strip())
            except Exception as exc:  # noqa: BLE001
                raise ConfigError(f"Invalid approved tag {raw!r}: {exc}") from exc
            if tag.value in seen:
                continue
            seen.add(tag.value)
            clean.append(tag.value)

        data = {
            "approved_tags": clean,
            "count": len(clean),
        }
        self._cache.write_json("04_final_tags", data)
        self._ctx.mark_done("approve", approved_count=len(clean))
        logger.info("Approved %d tags", len(clean))
        return data

    def status(self) -> dict[str, Any]:
        return self._ctx.snapshot()

    def close(self) -> None:
        try:
            self._llm.close()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to close LLM client")

    def __enter__(self) -> TagSummary:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
