from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Prompt:
    """Value Object для запроса к ИИ с поддержкой расширенных функций."""
    text: str
    system_prompt: str = ""
    enable_deep_think: bool = False
    enable_search: bool = False
    file_path: str = ""


@dataclass(frozen=True)
class AIResponse:
    """Value Object для ответа от ИИ."""
    text: str
    provider_name: str
    tokens_used: int = 0


class ILLMProvider(ABC):
    """Интерфейс провайдера ИИ."""
    
    @abstractmethod
    def get_name(self) -> str:
        """Возвращает имя провайдера."""
        pass
    
    @abstractmethod
    def send_prompt(self, prompt: Prompt) -> AIResponse:
        """Отправляет промпт и возвращает ответ."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Проверяет доступность провайдера."""
        pass


class IBrowserEngine(ABC):
    """Интерфейс для работы с браузером (адаптирован из ActantWeb)."""
    
    @abstractmethod
    def go_to(self, url: str) -> None:
        pass
    
    @abstractmethod
    def click(self, selector: str) -> None:
        pass
    
    @abstractmethod
    def type(self, selector: str, text: str) -> None:
        pass
    
    @abstractmethod
    def read(self, selector: str) -> str:
        pass
    
    @abstractmethod
    def wait(self, selector: str, timeout: int = 30) -> None:
        pass
    
    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def js(self, script: str) -> Any:
        pass

    @abstractmethod
    def upload_file(self, selector: str, file_path: str) -> None:
        """Специальный метод для надежной загрузки файлов в input[type='file']"""
        pass
