"""Порт чтения файлов vault.

Реализация ОБЯЗАНА использовать JasonUtils (JSON-команды read_files
и list_files). Прямое открытие файлов через pathlib/open запрещено —
это обходит Security Guard и логирование Jason.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class VaultFile:
    """Содержимое файла vault."""

    rel_path: str
    abs_path: str
    content: str
    has_frontmatter: bool
    tags: tuple[str, ...]


@runtime_checkable
class IFileReader(Protocol):
    """Чтение файлов vault через JasonUtils."""

    def list_markdown_files(self, *, exclude_dirs: tuple[str, ...]) -> list[str]:
        """Возвращает список rel_path всех .md файлов, кроме исключённых папок.

        Реализация оборачивает команду JasonUtils:
        {"command": "list_files", "params": {"paths": [...], "type": "files"}}
        """
        ...

    def read(self, rel_path: str) -> VaultFile:
        """Читает один файл.

        Реализация оборачивает команду JasonUtils:
        {"command": "read_files", "params": {"paths": [abs_path]}}

        Бросает FileReadError, если файл недоступен или Jason вернул error.
        """
        ...
