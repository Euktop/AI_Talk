from typing import List
from actantai.domain.ports import ILLMProvider, Prompt, AIResponse
from actantai.domain.exceptions import ProviderNotAvailableError


class ActantAIEngine:
    """Главный движок для работы с ИИ-провайдерами."""
    
    def __init__(self):
        self._providers: List[ILLMProvider] = []
    
    def register_provider(self, provider: ILLMProvider) -> None:
        """Регистрирует провайдера ИИ."""
        self._providers.append(provider)
    
    def get_provider(self, name: str) -> ILLMProvider:
        """Возвращает провайдер по имени."""
        for provider in self._providers:
            if provider.get_name().lower() == name.lower():
                return provider
        raise ProviderNotAvailableError(f"Провайдер '{name}' не найден")
    
    def list_providers(self) -> List[str]:
        """Возвращает список доступных провайдеров."""
        return [p.get_name() for p in self._providers]
    
    def ask(self, provider_name: str, text: str, system_prompt: str = "", enable_deep_think: bool = False, enable_search: bool = False) -> AIResponse:
        """Отправляет запрос к указанному провайдеру с поддержкой расширенных функций."""
        provider = self.get_provider(provider_name)
        if not provider.is_available():
            raise ProviderNotAvailableError(f"Провайдер '{provider_name}' недоступен")
        
        prompt = Prompt(
            text=text,
            system_prompt=system_prompt,
            enable_deep_think=enable_deep_think,
            enable_search=enable_search
        )
        return provider.send_prompt(prompt)
    
    def ask_all(self, text: str, system_prompt: str = "") -> List[AIResponse]:
        """Отправляет запрос ко всем зарегистрированным провайдерам."""
        responses = []
        prompt = Prompt(text=text, system_prompt=system_prompt)
        
        for provider in self._providers:
            if provider.is_available():
                try:
                    response = provider.send_prompt(prompt)
                    responses.append(response)
                except Exception as e:
                    print(f"Ошибка при запросе к {provider.get_name()}: {e}")
        
        return responses
