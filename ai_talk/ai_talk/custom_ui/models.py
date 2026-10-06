"""Модели данных CUSTOM UI."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Request:
    """Запрос к ИИ, ожидающий ответа пользователя."""

    id: str
    system_prompt: str
    user_prompt: str
    created_at: datetime
    answer: Optional[str] = None
    answered_at: Optional[datetime] = None

    def full_text(self) -> str:
        """Полный текст запроса: system + user (или что есть)."""
        if self.system_prompt and self.user_prompt:
            return self.system_prompt + "\n\n" + self.user_prompt
        return self.system_prompt or self.user_prompt or ""

    def preview(self, length: int = 80) -> str:
        """Однострочный обрезанный текст для списка."""
        text = self.full_text().replace("\n", " ").strip()
        if len(text) <= length:
            return text
        return text[:length] + "…"


@dataclass
class Client:
    """Зарегистрированный клиент (процесс, использующий сервер)."""

    id: str
    registered_at: datetime
