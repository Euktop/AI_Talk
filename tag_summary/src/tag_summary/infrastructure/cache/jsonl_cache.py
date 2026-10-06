"""Файловый JSON/JSONL кэш.

Кэш живёт вне vault — в tag_summary/runs/<timestamp>/. Прямая работа
с ФС через pathlib/open допустима.

read_jsonl терпим к повреждённым строкам: если последняя строка
оборвалась (краш в момент записи), она пропускается с warning.
Это критично для resume.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

from tag_summary.domain.exceptions import CacheError

logger = logging.getLogger(__name__)


class FileCacheStore:
    """Реализация ICacheStore поверх файлов в заданной директории."""

    def __init__(self, base_dir: Path) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._append_lock = threading.Lock()

    @property
    def base_dir(self) -> Path:
        return self._base

    def write_jsonl(self, name: str, rows: list[dict[str, Any]]) -> None:
        path = self._path(name, "jsonl")
        try:
            with path.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False))
                    fh.write("\n")
        except OSError as exc:
            raise CacheError(f"Failed to write {path}: {exc}") from exc
        logger.debug("Wrote %d rows to %s", len(rows), path)

    def append_jsonl(self, name: str, row: dict[str, Any]) -> None:
        path = self._path(name, "jsonl")
        with self._append_lock:
            try:
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False))
                    fh.write("\n")
            except OSError as exc:
                raise CacheError(f"Failed to append to {path}: {exc}") from exc

    def read_jsonl(self, name: str) -> list[dict[str, Any]]:
        path = self._path(name, "jsonl")
        if not path.exists():
            raise CacheError(f"Cache file does not exist: {path}")
        rows: list[dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning(
                            "Skipping unparsable line %d in %s (likely truncated write)",
                            line_no, path,
                        )
                        continue
        except OSError as exc:
            raise CacheError(f"Failed to read {path}: {exc}") from exc
        return rows

    def write_json(self, name: str, data: dict[str, Any]) -> None:
        path = self._path(name, "json")
        try:
            with path.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise CacheError(f"Failed to write {path}: {exc}") from exc

    def read_json(self, name: str) -> dict[str, Any]:
        path = self._path(name, "json")
        if not path.exists():
            raise CacheError(f"Cache file does not exist: {path}")
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise CacheError(f"Failed to read {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise CacheError(f"Expected JSON object in {path}, got {type(data).__name__}")
        return data

    def exists(self, name: str) -> bool:
        return self._path(name, "json").exists() or self._path(name, "jsonl").exists()

    def _path(self, name: str, ext: str) -> Path:
        return self._base / f"{name}.{ext}"
