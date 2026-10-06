"""Тесты structured_chat OllamaClient через mock — без реальной Ollama.

Проверяем, что structured_chat использует ai_talk.parsers.parse_json_object:
- принимает голый JSON;
- принимает JSON в markdown-блоке;
- на невалидном JSON бросает AITalkParsingError (не AITalkGenerationError).
"""
from unittest.mock import MagicMock, patch

import pytest

from ai_talk.domain.exceptions import AITalkParsingError
from ai_talk.domain.interfaces import Message
from ai_talk.infrastructure.ollama_client import OllamaClient


def _client_with_response(content):
    with patch("ai_talk.infrastructure.ollama_client.ollama.Client") as MockClient:
        instance = MagicMock()
        instance.list.return_value = {}
        instance.chat.return_value = {"message": {"content": content}}
        MockClient.return_value = instance
        client = OllamaClient(model="qwen2.5:3b")
    return client


def test_structured_chat_parses_plain_json():
    client = _client_with_response('{"ok": true}')
    result = client.structured_chat([Message(role="user", content="...")])
    assert result == {"ok": True}


def test_structured_chat_parses_markdown_fenced_json():
    client = _client_with_response('Результат:\n```json\n{"ok": true}\n```')
    result = client.structured_chat([Message(role="user", content="...")])
    assert result == {"ok": True}


def test_structured_chat_invalid_json_raises_parsing_error():
    client = _client_with_response("это не JSON")
    with pytest.raises(AITalkParsingError):
        client.structured_chat([Message(role="user", content="...")])
