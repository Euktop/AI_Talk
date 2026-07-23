from typing import Dict, Any
from ai_talk.domain.interfaces import ILLMClient, IFileReader, Message

class AskAIUseCase:
    def __init__(self, llm_client: ILLMClient, file_reader: IFileReader):
        self.llm_client = llm_client
        self.file_reader = file_reader

    def execute(self, source: str, system_prompt: str = "", temperature: float = 0.7) -> str:
        text = self.file_reader.read(source)
        messages = []
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))
        messages.append(Message(role="user", content=text))
        return self.llm_client.chat(messages, temperature)

    def execute_structured(self, source: str, system_prompt: str, response_format: str = "json") -> Dict[str, Any]:
        text = self.file_reader.read(source)
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=text)
        ]
        return self.llm_client.structured_chat(messages, response_format)

class GetTextUseCase:
    def __init__(self, file_reader: IFileReader):
        self.file_reader = file_reader

    def execute(self, source: str) -> str:
        return self.file_reader.read(source)
