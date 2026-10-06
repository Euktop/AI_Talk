"""Реализация IFileWriter через JasonUtils.

Стратегия:
1. Сформировать команду set_frontmatter.
2. Прогнать её через try (dry-run).
3. Если dry-run не дал ошибок — выполнить set_frontmatter.
4. Если dry-run дал ошибку — FileWriteError, файл не тронут.

Формат ответов JasonUtils (уточняется на живой системе):
- try             -> {"dry_run": true, "results": [{"command", "would_do", "error"}]}
                     либо просто список. Обрабатываем оба варианта.
- set_frontmatter -> обычно строка или dict. Считаем успехом, если нет явного error.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from tag_summary.domain.exceptions import FileWriteError
from tag_summary.domain.value_objects.tag import Tag
from tag_summary.infrastructure.jason.runner import JasonRunner

logger = logging.getLogger(__name__)


class JasonFileWriter:
    """Реализация IFileWriter через JasonUtils."""

    def __init__(self, *, vault_path: str, runner: JasonRunner) -> None:
        self._vault = Path(vault_path)
        self._runner = runner

    def set_tags(self, rel_path: str, tags: tuple[Tag, ...]) -> None:
        """Устанавливает поле tags (полная замена)."""
        abs_path = str(self._vault / rel_path.replace("/", "\\"))
        tag_values = [t.value for t in tags]

        set_cmd = {
            "command": "set_frontmatter",
            "params": {"path": abs_path, "fields": {"tags": tag_values}},
        }
        dry_cmd = {"command": "try", "params": {"commands": [set_cmd]}}

        try:
            dry_result = self._runner.run(dry_cmd)
        except Exception as exc:  # noqa: BLE001
            raise FileWriteError(
                f"Dry-run failed for {rel_path}: {exc}"
            ) from exc

        dry_errors = _collect_dry_run_errors(dry_result)
        if dry_errors:
            raise FileWriteError(
                f"Dry-run reported errors for {rel_path}: {'; '.join(dry_errors)}"
            )

        try:
            real_result = self._runner.run(set_cmd)
        except Exception as exc:  # noqa: BLE001
            raise FileWriteError(
                f"set_frontmatter failed for {rel_path}: {exc}"
            ) from exc

        real_error = _extract_error(real_result)
        if real_error:
            raise FileWriteError(
                f"set_frontmatter failed for {rel_path}: {real_error}"
            )

        logger.info("Tags applied to %s: %s", rel_path, tag_values)


def _collect_dry_run_errors(dry_result: Any) -> list[str]:
    """Извлекает список ошибок из ответа try.

    Ожидание: {"dry_run": true, "results": [{"command":..., "error": null}, ...]}.
    Также поддерживает: список результатов напрямую, {"result": [...]}.
    """
    inner: Any = None
    if isinstance(dry_result, dict):
        inner = dry_result.get("results")
        if inner is None:
            inner = dry_result.get("result")
    elif isinstance(dry_result, list):
        inner = dry_result

    if not isinstance(inner, list):
        return []

    errors: list[str] = []
    for entry in inner:
        if isinstance(entry, dict) and entry.get("error"):
            errors.append(str(entry["error"]))
    return errors


def _extract_error(real_result: Any) -> str | None:
    """Извлекает текст ошибки из ответа set_frontmatter.

    Если ответ — строка (типа "Файл изменён"), ошибки нет.
    Если dict с непустым error — возвращаем его.
    """
    if real_result is None:
        return None
    if isinstance(real_result, dict):
        err = real_result.get("error")
        if err:
            return str(err)
    return None
