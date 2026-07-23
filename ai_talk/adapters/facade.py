from typing import Union, Dict, Any
from ai_talk.config.models import ModelRole, MODEL_REGISTRY
from ai_talk.domain.interfaces import ILLMClient, IFileReader
from ai_talk.infrastructure.ollama_client import OllamaClient
from ai_talk.infrastructure.file_reader import LocalFileReader
from ai_talk.infrastructure.custom_client import CustomFileClient
from ai_talk.application.use_cases import AskAIUseCase, GetTextUseCase

class AITalk:
    def __init__(
        self,
        model: Union[str, ModelRole] = ModelRole.BASE,
        host: str = "http://localhost:11434",
        custom_dir: str = "запросы_к_ии"
    ):
        self.file_reader: IFileReader = LocalFileReader()
        
        if isinstance(model, ModelRole):
            model_name = MODEL_REGISTRY[model]
            if model == ModelRole.CUSTOM:
                self.llm_client: ILLMClient = CustomFileClient(custom_dir=custom_dir)
            else:
                self.llm_client: ILLMClient = OllamaClient(model=model_name, host=host)
        else:
            self.llm_client: ILLMClient = OllamaClient(model=model, host=host)

        self.ask_ai_use_case = AskAIUseCase(self.llm_client, self.file_reader)
        self.get_text_use_case = GetTextUseCase(self.file_reader)

    def ask_ai(self, source: str, system_prompt: str = "", temperature: float = 0.7) -> str:
        return self.ask_ai_use_case.execute(source, system_prompt, temperature)

    def ask_ai_structured(self, source: str, system_prompt: str, response_format: str = "json") -> Dict[str, Any]:
        return self.ask_ai_use_case.execute_structured(source, system_prompt, response_format)

    def get_text(self, source: str) -> str:
        return self.get_text_use_case.execute(source)
