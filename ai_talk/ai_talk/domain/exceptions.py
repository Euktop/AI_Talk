"""Совместимость: исключения переехали в ai_talk.errors.

См. docs/COMPATIBILITY.md. Импорт отсюда продолжает работать.
Канонический источник — ai_talk.errors.
"""
from ai_talk.errors import (
    AITalkConfigError,
    AITalkConnectionError,
    AITalkError,
    AITalkFileError,
    AITalkGenerationError,
    AITalkParsingError,
    AITalkTimeoutError,
)

__all__ = [
    "AITalkError",
    "AITalkConnectionError",
    "AITalkGenerationError",
    "AITalkParsingError",
    "AITalkTimeoutError",
    "AITalkFileError",
    "AITalkConfigError",
]
