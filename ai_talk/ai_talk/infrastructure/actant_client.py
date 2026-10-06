import sys
from typing import List, Dict, Any
import json

# Импорты из AI_Talk
from ai_talk.domain.interfaces import ILLMClient, Message
from ai_talk.domain.exceptions import AITalkGenerationError

class ActantAIClient(ILLMClient):
    """Адаптер, интегрирующий ActantAI (браузерные ИИ) в экосистему AI_Talk."""
    
    def __init__(self, provider_name: str = "DeepSeek", instance_id: int = 0):
        self.provider_name = provider_name
        self._browser_adapter = None
        self._engine = None
        self._initialize_browser(instance_id)

    def _initialize_browser(self, instance_id: int):
        """Инициализация браузера ActantAI.

        Импорты actantai/actantweb выполняются здесь, чтобы пакет ai_talk
        импортировался без установленного actantai (см. optional-dependencies).
        """
        try:
            from actantweb import create_actant
            from actantai.application.engine import ActantAIEngine
            from actantai.infrastructure.actantweb_adapter import ActantWebAdapter
            from actantai.infrastructure.providers.deepseek_provider import DeepSeekProvider

            actant_web = create_actant(instance_id=instance_id)
            self._browser_adapter = ActantWebAdapter(actant_web)
            self._engine = ActantAIEngine()
            
            if self.provider_name.lower() == "deepseek":
                self._engine.register_provider(DeepSeekProvider(self._browser_adapter))
            else:
                raise ValueError(f"Провайдер {self.provider_name} пока не реализован в адаптере")
                
        except Exception as e:
            raise AITalkGenerationError(f"Не удалось инициализировать браузер для ActantAI: {e}")

    def _prepare_prompt(self, messages: List[Message]):
        """Маппинг списка сообщений AI_Talk в объект Prompt от ActantAI."""
        from actantai.domain.ports import Prompt  # локальный импорт

        system_prompt = ""
        user_text_parts = []
        
        for msg in messages:
            if msg.role == "system":
                system_prompt += msg.content + "\n"
            elif msg.role == "user":
                user_text_parts.append(msg.content)
                
        final_text = "\n\n".join(user_text_parts) if user_text_parts else "Продолжи мысль."
        
        return Prompt(
            text=final_text,
            system_prompt=system_prompt.strip(),
            enable_deep_think=False,
            enable_search=False
        )

    def chat(self, messages: List[Message], temperature: float = 0.7) -> str:
        """Отправка запроса в веб-ИИ."""
        try:
            prompt = self._prepare_prompt(messages)
            response = self._engine.ask(self.provider_name, prompt.text, prompt.system_prompt)
            return response.text
        except Exception as e:
            raise AITalkGenerationError(f"Ошибка веб-генерации через ActantAI: {e}")

    def structured_chat(self, messages: List[Message], response_format: str = "json") -> Dict[str, Any]:
        """Веб-ИИ не всегда надежно возвращают JSON, но мы можем попросить его в промпте."""
        messages_with_json_req = messages.copy()
        messages_with_json_req.append(
            Message(role="user", content=f"Ответь СТРОГО в формате JSON. Не пиши ничего кроме валидного JSON. Схема: {response_format}")
        )
        raw_text = self.chat(messages_with_json_req)
        
        try:
            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except json.JSONDecodeError:
            raise AITalkGenerationError("Веб-ИИ вернул невалидный JSON.")

    def close(self):
        """Освобождение ресурсов браузера."""
        if self._browser_adapter:
            self._browser_adapter.stop()
            self._browser_adapter = None
