"""Тесты нового API AITalk (Фаза 4).

Все тесты работают через FakeLLMClient и FakeReader — реальная Ollama
не нужна. См. docs/API.md.
"""
import pytest

from ai_talk import AITalk, AITalkConfig

from conftest import FakeLLMClient


class FakeReader:
    def __init__(self, contents=None):
        self.contents = contents or {}

    def read(self, source):
        return self.contents.get(source, str(source))


def test_ask_returns_string_from_fake_client():
    fake = FakeLLMClient(chat_responses=["привет"])
    ai = AITalk(llm_client=fake)
    assert ai.ask("Привет") == "привет"
    assert len(fake.chat_calls) == 1
    messages, _ = fake.chat_calls[0]
    assert messages[-1].role == "user"
    assert messages[-1].content == "Привет"


def test_ask_with_system_prompt_includes_system_message():
    fake = FakeLLMClient(chat_responses=["ok"])
    ai = AITalk(llm_client=fake)
    ai.ask("Привет", system_prompt="Ты редактор")
    messages, _ = fake.chat_calls[0]
    assert messages[0].role == "system"
    assert messages[0].content == "Ты редактор"
    assert messages[1].role == "user"


def test_ask_with_source_reads_file():
    reader = FakeReader({"note.md": "тело файла"})
    fake = FakeLLMClient(chat_responses=["ok"])
    ai = AITalk(llm_client=fake, file_reader=reader)
    ai.ask("Разбери", source="note.md")
    messages, _ = fake.chat_calls[0]
    assert "Разбери" in messages[-1].content
    assert "тело файла" in messages[-1].content


def test_ask_file_delegates_to_ask():
    reader = FakeReader({"note.md": "тело"})
    fake = FakeLLMClient(chat_responses=["ok"])
    ai = AITalk(llm_client=fake, file_reader=reader)
    assert ai.ask_file("note.md") == "ok"
    messages, _ = fake.chat_calls[0]
    assert messages[-1].content == "тело"


def test_ask_json_uses_structured_chat():
    fake = FakeLLMClient(structured_responses=[{"a": 1}])
    ai = AITalk(llm_client=fake)
    assert ai.ask_json("дай json") == {"a": 1}
    assert len(fake.structured_calls) == 1
    _, response_format = fake.structured_calls[0]
    assert response_format == "json"


def test_ask_json_with_template_uses_system_prompt():
    fake = FakeLLMClient(structured_responses=[{"corrections": []}])
    ai = AITalk(llm_client=fake)
    result = ai.ask_json("проверь", template="spellcheck")
    assert result == {"corrections": []}
    messages, fmt = fake.structured_calls[0]
    assert fmt == "json"
    assert messages[0].role == "system"
    assert "редактор" in messages[0].content.lower()


def test_ask_json_with_unknown_template_raises():
    from ai_talk.errors import AITalkConfigError

    fake = FakeLLMClient()
    ai = AITalk(llm_client=fake)
    with pytest.raises(AITalkConfigError):
        ai.ask_json("x", template="nope")


def test_ask_uses_config_temperature():
    fake = FakeLLMClient(chat_responses=["ok"])
    cfg = AITalkConfig(temperature=0.1)
    ai = AITalk(llm_client=fake, config=cfg)
    ai.ask("q")
    _, temp = fake.chat_calls[0]
    assert temp == 0.1


def test_ask_explicit_temperature_overrides_config():
    fake = FakeLLMClient(chat_responses=["ok"])
    cfg = AITalkConfig(temperature=0.1)
    ai = AITalk(llm_client=fake, config=cfg)
    ai.ask("q", temperature=0.9)
    _, temp = fake.chat_calls[0]
    assert temp == 0.9


def test_health_check_returns_status_object():
    fake = FakeLLMClient()
    ai = AITalk(llm_client=fake)
    status = ai.health_check()
    assert isinstance(status.actantai_available, bool)
    assert isinstance(status.ollama_available, bool)
    assert isinstance(status.installed_models, list)
