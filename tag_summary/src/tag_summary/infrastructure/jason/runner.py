"""Обёртка над JasonUtils.

Использует JasonUtils.execute_command / execute_commands — они возвращают
результат напрямую, без временных файлов и без печати в stdout.

Форматы ответов по командам (проверено на живом JasonUtils):
- read_files    -> list[{"path", "status", "content", "resolved"}]
- list_files    -> {"items": [...], "errors": [...]} (уточняется)
- set_frontmatter -> dict или строка (уточняется)
- try           -> {"dry_run": true, "results": [...]} (уточняется)

Поэтому run() возвращает Any — вызывающий код сам разбирает свой формат.

Thread-safe: параллельные LLM-запросы разрешены, параллельные вызовы
Jason сериализуются через lock (JasonUtils не потокобезопасен).
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from tag_summary.domain.exceptions import ConfigError, TagSummaryError

logger = logging.getLogger(__name__)

try:
    from jasonutils import JasonUtils as _JasonUtils  # type: ignore
    _JASON_AVAILABLE = True
except ImportError:  # pragma: no cover
    _JasonUtils = None  # type: ignore[assignment]
    _JASON_AVAILABLE = False


class JasonRunner:
    """Выполняет JSON-команды через JasonUtils. Thread-safe."""

    def __init__(self) -> None:
        if not _JASON_AVAILABLE:
            raise ConfigError(
                "jasonutils package is not installed or has no public API. "
                "Run: pip install -e D:/repos/Jason/jasonutils"
            )
        self._utils = _JasonUtils()
        self._lock = threading.Lock()

    def run(self, command: dict[str, Any]) -> Any:
        """Выполняет одну команду и возвращает результат execute_command.

        Формат ответа зависит от команды. Никакой нормализации — вызывающий
        код сам знает, что ожидать.
        """
        with self._lock:
            try:
                result = self._utils.execute_command(command)
            except Exception as exc:  # noqa: BLE001
                raise TagSummaryError(
                    f"JasonUtils command failed: {command.get('command')!r}: {exc}"
                ) from exc
        return result

    def run_batch(self, commands: list[dict[str, Any]]) -> list[Any]:
        """Выполняет список команд. Возвращает список результатов."""
        if not commands:
            return []
        with self._lock:
            try:
                results = self._utils.execute_commands(commands)
            except Exception as exc:  # noqa: BLE001
                raise TagSummaryError(
                    f"JasonUtils batch failed: {exc}"
                ) from exc
        if results is None:
            return []
        if not isinstance(results, list):
            return [results]
        return results
