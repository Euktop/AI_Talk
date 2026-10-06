"""Порт получения промптов из Obsidian через Command Engine.

Правило (согласовано 2026-09-20):
Промпт возвращается БЕЗ подстановки данных. Command Engine читает
только шаблон инструкции. Данные (содержимое файла, JSON-списки)
приклеиваются в Python отдельно.

Причина: если данные содержат [[wiki-links]] или {{vars}}, Command
Engine попытается их разрешить при подстановке и вернёт маркер ошибки,
что сломает запрос.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IPromptProvider(Protocol):
    """Контракт провайдера промптов."""

    def get_collect_prompt(self) -> str:
        """Инструкция для сбора тегов-кандидатов."""
        ...

    def get_cluster_prompt(self) -> str:
        """Инструкция для кластеризации тегов."""
        ...

    def get_apply_prompt(self) -> str:
        """Инструкция для выбора финальных тегов."""
        ...
