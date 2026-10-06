import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ai_talk.config import AITalkConfig
from ai_talk.config.models import MODEL_REGISTRY, ModelRole
from ai_talk.domain.interfaces import IFileReader, ILLMClient, Message
from ai_talk.infrastructure.custom_web_client import CustomWebClient
from ai_talk.infrastructure.file_reader import LocalFileReader
from ai_talk.infrastructure.ollama_client import OllamaClient
from ai_talk.application.use_cases import AskAIUseCase, GetTextUseCase
from ai_talk.templates import TemplateRegistry, TemplateSpec, default_registry


@dataclass
class HealthStatus:
    """Результат AITalk.health_check()."""

    ollama_available: bool
    installed_models: List[str]
    actantai_available: bool


class AITalk:
    """Фасад AI_Talk.

    Совместимость (docs/COMPATIBILITY.md): позиционные параметры конструктора
    и сигнатуры ask_ai / ask_ai_structured / get_text / close не менялись.
    Новые параметры и методы добавлены как keyword-only / новые имена.
    """

    def __init__(
        self,
        model: Union[str, ModelRole] = ModelRole.BASE,
        host: str = "http://localhost:11434",
        custom_dir: str = "запросы_к_ии",
        browser_instance_id: int = 0,
        *,
        config: Optional[AITalkConfig] = None,
        llm_client: Optional[ILLMClient] = None,
        file_reader: Optional[IFileReader] = None,
        template_registry: Optional[TemplateRegistry] = None,
    ):
        self.template_registry: TemplateRegistry = (
            template_registry if template_registry is not None else default_registry()
        )
        if config is not None:
            self._config = config
            effective_model: Union[str, ModelRole] = config.model_role
            effective_host = config.ollama_host
            effective_custom_dir = str(config.custom_dir)
        else:
            self._config = AITalkConfig(
                model_role=model,
                ollama_host=host,
                custom_dir=Path(custom_dir),
            )
            effective_model = model
            effective_host = host
            effective_custom_dir = custom_dir

        self.file_reader: IFileReader = (
            file_reader if file_reader is not None else LocalFileReader()
        )

        if llm_client is not None:
            self.llm_client: ILLMClient = llm_client
        else:
            self.llm_client = self._build_default_client(
                effective_model,
                effective_host,
                effective_custom_dir,
                browser_instance_id,
                config=self._config,
            )

        self.ask_ai_use_case = AskAIUseCase(self.llm_client, self.file_reader)
        self.get_text_use_case = GetTextUseCase(self.file_reader)

    @staticmethod
    def _build_default_client(
        model: Union[str, ModelRole],
        host: str,
        custom_dir: str,
        browser_instance_id: int,
        config: Optional[AITalkConfig] = None,
    ) -> ILLMClient:
        if isinstance(model, ModelRole):
            if model == ModelRole.CUSTOM:
                if config is not None:
                    return CustomWebClient(
                        host=config.custom_ui_host,
                        port=config.custom_ui_port,
                        db_path=config.custom_ui_db,
                        open_browser=config.custom_ui_open_browser,
                    )
                return CustomWebClient()
            if model in (ModelRole.WEB_DEEPSEEK, ModelRole.WEB_CHATGPT):
                # Lazy-импорт: ai_talk импортируется без установленного actantai.
                from ai_talk.infrastructure.actant_client import ActantAIClient
                provider_name = (
                    "DeepSeek" if model == ModelRole.WEB_DEEPSEEK else "ChatGPT"
                )
                return ActantAIClient(
                    provider_name=provider_name,
                    instance_id=browser_instance_id,
                )
            return OllamaClient(model=MODEL_REGISTRY[model], host=host)
        return OllamaClient(model=model, host=host)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Закрывает ресурсы, если клиент требует освобождения (например, браузер)."""
        if hasattr(self.llm_client, 'close') and callable(self.llm_client.close):
            self.llm_client.close()

    # -------- Старый API (не менять) --------

    def ask_ai(self, source: str, system_prompt: str = "", temperature: float = 0.7) -> str:
        return self.ask_ai_use_case.execute(source, system_prompt, temperature)

    def ask_ai_structured(
        self, source: str, system_prompt: str, response_format: str = "json"
    ) -> Dict[str, Any]:
        return self.ask_ai_use_case.execute_structured(source, system_prompt, response_format)

    def get_text(self, source: str) -> str:
        return self.get_text_use_case.execute(source)

    # -------- Новый API (Фаза 4) --------

    def _resolve_temperature(self, temperature: Optional[float]) -> float:
        return temperature if temperature is not None else self._config.temperature

    def _build_user_messages(
        self, prompt: str, source: Optional[Union[str, Path]], system_prompt: str
    ) -> List[Message]:
        if source is not None:
            text = self.file_reader.read(str(source))
            full_prompt = prompt + "\n\n" + text if prompt else text
        else:
            full_prompt = prompt

        messages: List[Message] = []
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))
        messages.append(Message(role="user", content=full_prompt))
        return messages

    def ask(
        self,
        prompt: str,
        *,
        source: Optional[Union[str, Path]] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Запрос к LLM. Возвращает str.

        Если source задан — читает его и добавляет к prompt.
        """
        messages = self._build_user_messages(prompt, source, system_prompt or "")
        return self.llm_client.chat(messages, self._resolve_temperature(temperature))

    def ask_file(
        self, path: Union[str, Path], *, system_prompt: Optional[str] = None
    ) -> str:
        """Синоним ask("", source=path, system_prompt=...). Возвращает str."""
        return self.ask("", source=path, system_prompt=system_prompt)

    def ask_many(
        self,
        prompts: List[str],
        *,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_workers: int = 8,
    ) -> List[str]:
        """Отправляет несколько запросов параллельно.

        В CUSTOM-режиме все запросы появляются в UI сразу, пользователь
        отвечает в любом порядке. Возвращает список ответов в порядке prompts.

        В Ollama-режиме просто параллельные вызовы одного и того же клиента;
        параллелизм ограничен max_workers.
        """
        from concurrent.futures import ThreadPoolExecutor

        if not prompts:
            return []
        n = min(max_workers, len(prompts))
        with ThreadPoolExecutor(max_workers=n) as ex:
            futures = [
                ex.submit(
                    self.ask,
                    p,
                    system_prompt=system_prompt,
                    temperature=temperature,
                )
                for p in prompts
            ]
            return [f.result() for f in futures]

    def ask_json(
        self,
        prompt: str,
        *,
        source: Optional[Union[str, Path]] = None,
        schema: Optional[type] = None,
        template: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Структурированный запрос. Возвращает dict.

        schema пока принимается, но не валидируется (см. docs/API.md).
        template будет реализован в Фазе 5 (docs/MIGRATION.md).
        """
        if template is not None:
            spec = self.template_registry.get(template)
            messages = self._build_user_messages(prompt, source, spec.system_prompt)
            return self.llm_client.structured_chat(messages, "json")
        messages = self._build_user_messages(prompt, source, "")
        return self.llm_client.structured_chat(messages, "json")

    def run_template(
        self,
        name: str,
        *,
        source: Optional[Union[str, Path]] = None,
        prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Any:
        """Запускает именованный шаблон. Возвращает str или dict.

        Текст или JSON — по spec.output_format. Температура:
        аргумент > spec.temperature > config.temperature.
        """
        spec = self.template_registry.get(name)
        messages = self._build_user_messages(prompt or "", source, spec.system_prompt)
        if spec.output_format == "json":
            return self.llm_client.structured_chat(messages, "json")
        effective = temperature if temperature is not None else spec.temperature
        return self.llm_client.chat(messages, self._resolve_temperature(effective))

    def register_template(self, spec: TemplateSpec) -> None:
        """Регистрирует шаблон. Переопределяет встроенный с тем же именем."""
        self.template_registry.register(spec)

    def health_check(self) -> HealthStatus:
        """Диагностика окружения. Не блокирует."""
        ollama_ok = False
        models: List[str] = []
        if isinstance(self.llm_client, OllamaClient):
            try:
                response = self.llm_client.client.list()
                raw_models = response.get("models", []) or []
                models = [
                    m.get("name") or m.get("model") or ""
                    for m in raw_models
                ]
                models = [name for name in models if name]
                ollama_ok = True
            except Exception:
                ollama_ok = False
        actantai_ok = importlib.util.find_spec("actantai") is not None
        return HealthStatus(
            ollama_available=ollama_ok,
            installed_models=models,
            actantai_available=actantai_ok,
        )
