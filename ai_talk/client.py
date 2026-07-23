import logging
import json
from typing import Dict, Any, Optional
import ollama

from .exceptions import AITalkConnectionError, AITalkGenerationError

logger = logging.getLogger("AI_Talk")

class AITalk:
    """Главный клиент для взаимодействия с локальной LLM через Ollama."""
    
    def __init__(self, model: str = "qwen2.5:3b", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host
        self.client = ollama.Client(host=self.host)
        self._check_connection()

    def _check_connection(self):
        try:
            self.client.list()
            logger.info(f"✅ Успешное подключение к Ollama. Модель: {self.model}")
        except Exception as e:
            raise AITalkConnectionError(f"Не удалось подключиться к Ollama по адресу {self.host}.") from e

    def chat(self, user_message: str, system_prompt: Optional[str] = None, temperature: float = 0.7) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        try:
            response = self.client.chat(model=self.model, messages=messages, options={"temperature": temperature})
            return response['message']['content'].strip()
        except Exception as e:
            raise AITalkGenerationError(f"Ошибка при генерации текста: {e}") from e

    def structured_chat(self, user_message: str, system_prompt: str, response_format: str = "json") -> Dict[str, Any]:
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]
        try:
            response = self.client.chat(model=self.model, messages=messages, format=response_format)
            raw_json = response['message']['content'].strip()
            return json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise AITalkGenerationError(f"Модель вернула невалидный JSON: {raw_json}") from e
        except Exception as e:
            raise AITalkGenerationError(f"Ошибка структурированной генерации: {e}") from e