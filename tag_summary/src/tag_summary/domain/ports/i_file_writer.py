"""Порт записи изменений в vault.

Реализация ОБЯЗАНА использовать JasonUtils (команда set_frontmatter).
Прямая запись в ФС запрещена — обходит rollback, логирование и
Security Guard Jason.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from tag_summary.domain.value_objects.tag import Tag


@runtime_checkable
class IFileWriter(Protocol):
    """Изменение frontmatter файлов vault через JasonUtils."""

    def set_tags(self, rel_path: str, tags: tuple[Tag, ...]) -> None:
        """Устанавливает поле tags в frontmatter (полная замена).

        Правила:
        - существующий список tags перезаписывается целиком;
        - если frontmatter отсутствует — создаётся;
        - если frontmatter есть, а tags нет — добавляется.

        Реализация оборачивает команду JasonUtils:
        {
          "command": "set_frontmatter",
          "params": {
            "path": "<abs_path>",
            "fields": {"tags": ["<tag1>", "<tag2>", ...]}
          }
        }

        Перед применением ОБЯЗАТЕЛЕН dry-run через команду try.
        Бросает FileWriteError при ошибке Jason.
        """
        ...
