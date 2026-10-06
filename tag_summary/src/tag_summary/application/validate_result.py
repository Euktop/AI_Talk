"""Use case: валидация применённых тегов.

Читает 05_applied.jsonl, проверяет что каждый применённый тег валиден
по Tag, собирает статистику по структурным и семантическим тегам.
Запускает внешний ObsidianValidator (если доступен) через subprocess,
чтобы получить отчёт о состоянии всего vault.

Не модифицирует файлы. Только чтение и отчёт.
"""

from __future__ import annotations

import logging
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from tag_summary.application.apply_final_tags import ARTIFACT_NAME as APPLIED_ARTIFACT
from tag_summary.application.context import RunContext
from tag_summary.domain.exceptions import CacheError
from tag_summary.domain.services.structural_tag_resolver import StructuralTagResolver
from tag_summary.domain.value_objects.tag import Tag

logger = logging.getLogger(__name__)

ARTIFACT_NAME = "06_validation"


class ValidateResultUseCase:
    """Валидирует результаты применения тегов."""

    def __init__(
        self,
        *,
        validator_script: str | None = None,
        resolver: StructuralTagResolver | None = None,
    ) -> None:
        self._validator_script = validator_script
        self._resolver = resolver or StructuralTagResolver()

    def execute(self, ctx: RunContext) -> dict[str, Any]:
        ctx.mark_started("validate")

        try:
            rows = ctx.cache_store.read_jsonl(APPLIED_ARTIFACT)
        except CacheError as exc:
            ctx.mark_failed("validate", str(exc))
            raise

        issues: list[dict[str, Any]] = []
        semantic_counts: Counter[str] = Counter()
        structural_counts: Counter[str] = Counter()
        applied = 0
        skipped = 0

        for row in rows:
            path = str(row.get("path") or "")
            status = row.get("status")
            if status == "skipped":
                skipped += 1
                continue
            if status != "applied":
                continue
            applied += 1

            structural = {t.value for t in self._resolver.resolve(path)}
            for raw in row.get("tags") or []:
                try:
                    tag = Tag(str(raw))
                except Exception as exc:  # noqa: BLE001
                    issues.append({
                        "path": path,
                        "tag": raw,
                        "error": str(exc),
                    })
                    continue
                if tag.value in structural:
                    structural_counts[tag.value] += 1
                else:
                    semantic_counts[tag.value] += 1

        external_report = self._run_external_validator(ctx.vault_path)

        result = {
            "files_applied": applied,
            "files_skipped": skipped,
            "invalid_tags": len(issues),
            "issues": issues,
            "semantic_tag_frequency": dict(semantic_counts.most_common()),
            "structural_tag_frequency": dict(structural_counts.most_common()),
            "external_validator": external_report,
        }
        ctx.cache_store.write_json(ARTIFACT_NAME, result)
        ctx.mark_done(
            "validate",
            files_applied=applied,
            files_skipped=skipped,
            invalid_tags=len(issues),
        )
        logger.info(
            "Validate: applied=%d, skipped=%d, invalid_tags=%d",
            applied, skipped, len(issues),
        )
        return result

    def _run_external_validator(self, vault_path: str) -> dict[str, Any]:
        """Запускает ObsidianValidator, если путь к скрипту задан."""
        if not self._validator_script:
            return {"status": "skipped", "reason": "no_validator_configured"}

        script = Path(self._validator_script)
        if not script.exists():
            logger.warning("External validator not found: %s", script)
            return {"status": "skipped", "reason": "validator_not_found"}

        try:
            completed = subprocess.run(
                ["python", str(script)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=300,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.exception("External validator failed to start")
            return {"status": "error", "error": str(exc)}

        return {
            "status": "ok" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-500:] if completed.stdout else "",
            "stderr_tail": completed.stderr[-500:] if completed.stderr else "",
        }
