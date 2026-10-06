"""Доменные исключения tag_summary.

Все исключения наследуются от TagSummaryError, чтобы внешние слои
могли ловить любую ошибку пайплайна одним except.
"""


class TagSummaryError(Exception):
    """Базовое исключение для всего пакета."""


class LLMError(TagSummaryError):
    """Ошибка на уровне LLM (сеть, недоступность, таймаут)."""


class LLMFormatError(LLMError):
    """LLM не смогла выдать ожидаемый формат после 3 ретраев."""


class FileReadError(TagSummaryError):
    """Не удалось прочитать файл vault."""


class FileWriteError(TagSummaryError):
    """Не удалось записать изменения в файл vault."""


class CacheError(TagSummaryError):
    """Ошибка чтения/записи промежуточного кэша."""


class ConfigError(TagSummaryError):
    """Ошибка в конфигурации запуска."""


class ValidationError(TagSummaryError):
    """Нарушение инварианта (невалидный тег, пустой кластер и т.д.)."""
