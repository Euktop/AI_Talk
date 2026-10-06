"""Реализация IFileReader через JasonUtils.

Форматы ответов (проверено на живом JasonUtils через execute_command):
- read_files  -> list[{"path", "status", "content", "resolved"}]
                 Каждый файл — отдельный элемент. status="ok" или "error".
- list_files  -> {"items": ["abs path", ...], "errors": [...]}

Парсер frontmatter — минимальный, через PyYAML.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from tag_summary.domain.exceptions import FileReadError
from tag_summary.domain.ports.i_file_reader import VaultFile
from tag_summary.infrastructure.jason.runner import JasonRunner

logger = logging.getLogger(__name__)


class JasonFileReader:
    """Реализация IFileReader через JasonUtils."""

    def __init__(self, *, vault_path: str, runner: JasonRunner) -> None:
        self._vault = Path(vault_path)
        self._runner = runner

    def list_markdown_files(self, *, exclude_dirs: tuple[str, ...]) -> list[str]:
        """Возвращает rel_path всех .md файлов, кроме исключённых папок."""
        command = {
            "command": "list_files",
            "params": {
                "paths": [str(self._vault)],
                "depth": 0,
                "type": "files",
            },
        }
        result = self._runner.run(command)
        items = _extract_items(result)
        if not items:
            raise FileReadError(
                f"list_files returned no items. Raw result type: {type(result).__name__}"
            )

        vault_prefix = str(self._vault).rstrip("\\/") + "\\"
        md_files: list[str] = []
        for abs_str in items:
            s = str(abs_str)
            if not s.lower().endswith(".md"):
                continue
            rel = s[len(vault_prefix):] if s.startswith(vault_prefix) else s
            rel = rel.replace("\\", "/")
            if self._is_excluded(rel, exclude_dirs):
                continue
            md_files.append(rel)
        md_files.sort()
        logger.info("Discovered %d markdown files", len(md_files))
        return md_files

    def read(self, rel_path: str) -> VaultFile:
        """Читает один файл через Jason read_files."""
        abs_path = str(self._vault / rel_path.replace("/", "\\"))
        command = {
            "command": "read_files",
            "params": {"paths": [abs_path]},
        }
        result = self._runner.run(command)
        entry = _extract_read_entry(result, rel_path)

        if isinstance(entry, dict) and entry.get("status") == "error":
            raise FileReadError(
                f"read_files error for {rel_path}: {entry.get('error', 'unknown')}"
            )

        content = entry.get("content") or "" if isinstance(entry, dict) else ""
        has_fm, tags = _parse_frontmatter(content)
        return VaultFile(
            rel_path=rel_path,
            abs_path=abs_path,
            content=content,
            has_frontmatter=has_fm,
            tags=tags,
        )

    @staticmethod
    def _is_excluded(rel_path: str, exclude_dirs: tuple[str, ...]) -> bool:
        for prefix in exclude_dirs:
            p = prefix.rstrip("/") + "/"
            if rel_path == prefix.rstrip("/") or rel_path.startswith(p):
                return True
        return False


def _extract_items(result: Any) -> list[str]:
    """Извлекает список путей из ответа list_files.

    Ожидание: {"items": [...]} или [...] или {"result": {"items": [...]}}.
    """
    if result is None:
        return []
    if isinstance(result, dict):
        inner = result.get("items")
        if isinstance(inner, list):
            return [str(x) for x in inner]
        inner = result.get("result")
        if isinstance(inner, dict):
            items = inner.get("items")
            if isinstance(items, list):
                return [str(x) for x in items]
        if isinstance(inner, list):
            return [str(x) for x in inner]
        return []
    if isinstance(result, list):
        return [str(x) for x in result]
    return []


def _extract_read_entry(result: Any, rel_path: str) -> dict:
    """Извлекает запись одного файла из ответа read_files.

    Ожидание: [{"path":..., "status":"ok", "content":...}].
    Также поддерживается {"result": [...]} для совместимости.
    """
    if result is None:
        raise FileReadError(f"read_files returned None for {rel_path}")

    if isinstance(result, dict):
        inner = result.get("result")
        if isinstance(inner, list) and inner:
            first = inner[0]
            if isinstance(first, dict):
                return first
        if "content" in result or "status" in result:
            return result

    if isinstance(result, list):
        if not result:
            raise FileReadError(f"read_files returned empty list for {rel_path}")
        first = result[0]
        if isinstance(first, dict):
            return first

    raise FileReadError(
        f"read_files unexpected result type for {rel_path}: {type(result).__name__}"
    )


def _parse_frontmatter(content: str) -> tuple[bool, tuple[str, ...]]:
    """Возвращает (has_frontmatter, tags)."""
    if not content.startswith("---"):
        return False, ()

    lines = content.splitlines()
    if len(lines) < 2 or lines[0].strip() != "---":
        return False, ()

    end_index = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_index = i
            break
    if end_index == -1:
        return False, ()

    yaml_text = "\n".join(lines[1:end_index])
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        logger.warning("Failed to parse frontmatter YAML, treating as empty")
        return True, ()
    if not isinstance(data, dict):
        return True, ()

    raw_tags = data.get("tags")
    if raw_tags is None:
        return True, ()
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    if not isinstance(raw_tags, list):
        return True, ()
    tags = tuple(str(t).lstrip("#") for t in raw_tags if t)
    return True, tags
