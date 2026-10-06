"""Порт промежуточного кэша между этапами пайплайна.

Кэш живёт вне vault, в tag_summary/runs/<timestamp>/. Прямая ФС
допустима. JasonUtils здесь не используется.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ICacheStore(Protocol):
    """JSONL + JSON хранилище для промежуточных результатов."""

    def write_jsonl(self, name: str, rows: list[dict[str, Any]]) -> None:
        """Перезаписывает файл <name>.jsonl целиком."""
        ...

    def append_jsonl(self, name: str, row: dict[str, Any]) -> None:
        """Дописывает одну строку в конец <name>.jsonl (создаёт, если нет)."""
        ...

    def read_jsonl(self, name: str) -> list[dict[str, Any]]:
        """Читает <name>.jsonl. Пропускает повреждённые строки с warning."""
        ...

    def write_json(self, name: str, data: dict[str, Any]) -> None:
        """Пишет словарь в <name>.json (полная перезапись)."""
        ...

    def read_json(self, name: str) -> dict[str, Any]:
        """Читает <name>.json."""
        ...

    def exists(self, name: str) -> bool:
        """Проверяет наличие артефакта (.json или .jsonl)."""
        ...
