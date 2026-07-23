import ollama
from pathlib import Path
from typing import Union
from .exceptions import AITalkConnectionError, AITalkGenerationError
from .models import ModelRole, MODEL_REGISTRY

class AITalk:
    """
    Локальная библиотека для работы с Ollama.
    Умеет принимать как путь к файлу, так и обычный текст.
    Поддерживает абстракцию моделей через ModelRole.
    """
    
    def __init__(self, model: Union[str, ModelRole] = ModelRole.BASE, host: str = "http://localhost:11434"):
        # Определяем реальное имя модели
        if isinstance(model, ModelRole):
            self.model_name = MODEL_REGISTRY[model]
        else:
            self.model_name = model
            
        self.client = ollama.Client(host=host)
        self._check_connection()

    def _check_connection(self):
        """Проверка доступности Ollama при инициализации."""
        try:
            self.client.list()
        except Exception as e:
            raise AITalkConnectionError(
                f"Не удалось подключиться к Ollama ({self.client.host}). "
                "Убедитесь, что Ollama запущена."
            ) from e

    def _resolve_source(self, source: Union[str, Path]) -> str:
        """
        Внутренний парсер. 
        Если передан путь к существующему файлу — читает его.
        Иначе считает, что передан просто текст.
        """
        path = Path(source)
        if path.exists() and path.is_file():
            return path.read_text(encoding='utf-8')
        return str(source)

    def get_text(self, source: Union[str, Path]) -> str:
        """
        Читает файл (или принимает сырой текст) и возвращает чистую строку.
        """
        return self._resolve_source(source)

    def ask_ai(
        self, 
        source: Union[str, Path], 
        system_prompt: str = "", 
        temperature: float = 0.7
    ) -> str:
        """
        Читает файл (или принимает сырой текст), отправляет его в ИИ 
        и возвращает ответ нейросети.
        """
        text = self._resolve_source(source)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": text})

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=messages,
                options={"temperature": temperature}
            )
            return response['message']['content'].strip()
        except Exception as e:
            raise AITalkGenerationError(f"Ошибка генерации ИИ: {e}") from e