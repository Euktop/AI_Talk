import json
import ollama
from typing import List, Dict, Any
from ai_talk.domain.interfaces import ILLMClient, Message
from ai_talk.domain.exceptions import AITalkConnectionError, AITalkGenerationError

class OllamaClient:
    def __init__(self, model: str, host: str = "http://localhost:11434"):
        self.model = model
        self.host = host
        self.client = ollama.Client(host=self.host)
        self._check_connection()

    def _check_connection(self):
        try:
            self.client.list()
        except Exception as e:
            raise AITalkConnectionError(f"Не удалось подключиться к Ollama ({self.host}).") from e

    def chat(self, messages: List[Message], temperature: float = 0.7) -> str:
        try:
            payload = [{"role": m.role, "content": m.content} for m in messages]
            response = self.client.chat(model=self.model, messages=payload, options={"temperature": temperature})
            return response['message']['content'].strip()
        except Exception as e:
            raise AITalkGenerationError(f"Ошибка генерации ИИ: {e}") from e

    def structured_chat(self, messages: List[Message], response_format: str = "json") -> Dict[str, Any]:
        try:
            payload = [{"role": m.role, "content": m.content} for m in messages]
            response = self.client.chat(model=self.model, messages=payload, format=response_format)
            return json.loads(response['message']['content'].strip())
        except Exception as e:
            raise AITalkGenerationError(f"Ошибка структурированной генерации: {e}") from e
