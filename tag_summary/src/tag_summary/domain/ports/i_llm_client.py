"""Порт доступа к LLM. Реализация — обёртка над ai_talk.AITalk."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ILLMClient(Protocol):
    """Контракт клиента LLM.

    Запросы всегда выполняются с требованием JSON-ответа.
    При невалидном JSON — 3 ретрая, затем LLMFormatError.
    """

    def ask_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_retries: int = 3,
    ) -> str:
        """Возвращает сырой текст ответа (валидный JSON).

        model — 'fast' или 'smart' (роль из AI_Talk).
        Бросает LLMError / LLMFormatError.
        """
        ...
