r"""Pytest-конфигурация для тестов ai_talk.

Проект лежит внутри монорепы D:\repos\AI_Talk. Если pytest запускается
из корня монорепы, Python видит каталог 'ai_talk/' (корень проекта, без
__init__.py) как namespace-пакет и импортирует пустышку вместо реального
пакета 'ai_talk/ai_talk/'.

Этот conftest ставит корень проекта первым в sys.path, чтобы
'import ai_talk' всегда находил настоящий пакет независимо от CWD.
"""
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


class FakeLLMClient:
    """Реализация ILLMClient Protocol для тестов без реальной Ollama.

    Позволяет задать заранее подготовленные ответы и проверить, какие
    сообщения были отправлены. Используется в тестах AITalk (Фаза 4+).
    """

    def __init__(self, chat_responses=None, structured_responses=None):
        self.chat_responses = list(chat_responses or [])
        self.structured_responses = list(structured_responses or [])
        self.chat_calls = []
        self.structured_calls = []

    def chat(self, messages, temperature=0.7):
        self.chat_calls.append((list(messages), temperature))
        if not self.chat_responses:
            raise AssertionError("FakeLLMClient: chat_responses исчерпаны")
        return self.chat_responses.pop(0)

    def structured_chat(self, messages, response_format="json"):
        self.structured_calls.append((list(messages), response_format))
        if not self.structured_responses:
            raise AssertionError("FakeLLMClient: structured_responses исчерпаны")
        return self.structured_responses.pop(0)
