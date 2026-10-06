"""Иерархия исключений AI_Talk.

Совместимость (docs/COMPATIBILITY.md):
- AITalkError, AITalkConnectionError, AITalkGenerationError — публичные,
  нельзя удалять или менять их базовые связи.
- Новые классы (AITalkParsingError, AITalkTimeoutError) — наследники
  AITalkGenerationError, чтобы старые `except AITalkGenerationError`
  продолжали ловить парсинг и таймауты.
"""


class AITalkError(Exception):
    """Базовая ошибка библиотеки."""
    pass


class AITalkConnectionError(AITalkError):
    """Ошибка подключения к LLM (Ollama, браузер, сеть)."""
    pass


class AITalkGenerationError(AITalkError):
    """Ошибка при запросе к ИИ (генерация, ответ, парсинг)."""
    pass


class AITalkParsingError(AITalkGenerationError):
    """Модель вернула невалидный JSON или ответ не содержит JSON.

    Наследник AITalkGenerationError для обратной совместимости.
    """
    pass


class AITalkTimeoutError(AITalkGenerationError):
    """Ответ не получен за отведённое время.

    Наследник AITalkGenerationError для обратной совместимости.
    """
    pass


class AITalkFileError(AITalkError):
    """Ошибка файловых операций (чтение, запись, перемещение)."""
    pass


class AITalkConfigError(AITalkError):
    """Некорректная конфигурация."""
    pass


__all__ = [
    "AITalkError",
    "AITalkConnectionError",
    "AITalkGenerationError",
    "AITalkParsingError",
    "AITalkTimeoutError",
    "AITalkFileError",
    "AITalkConfigError",
]
