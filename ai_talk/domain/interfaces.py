from typing import Protocol, List, Dict, Any

class Message:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

class ILLMClient(Protocol):
    def chat(self, messages: List[Message], temperature: float = 0.7) -> str: ...
    def structured_chat(self, messages: List[Message], response_format: str = "json") -> Dict[str, Any]: ...

class IFileReader(Protocol):
    def read(self, source: str) -> str: ...
