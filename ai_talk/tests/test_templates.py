"""Тесты реестра шаблонов и AITalk.run_template (Фаза 5)."""
import pytest

from ai_talk import (
    AITalk,
    TemplateRegistry,
    TemplateSpec,
    default_registry,
)
from ai_talk.errors import AITalkConfigError

from conftest import FakeLLMClient


def test_default_registry_contains_builtin_templates():
    r = default_registry()
    assert "spellcheck" in r
    assert "obsidian_tagger" in r
    assert r.names() == ["obsidian_tagger", "spellcheck"]


def test_default_registry_returns_fresh_instance_each_time():
    r1 = default_registry()
    r2 = default_registry()
    assert r1 is not r2
    r1.register(TemplateSpec(name="custom", system_prompt="x"))
    assert "custom" not in r2


def test_register_and_get():
    r = TemplateRegistry()
    spec = TemplateSpec(name="x", system_prompt="sys", output_format="json")
    r.register(spec)
    assert r.get("x") is spec
    assert "x" in r


def test_get_unknown_raises_config_error():
    r = TemplateRegistry()
    with pytest.raises(AITalkConfigError):
        r.get("nope")


def test_register_invalid_output_format_raises():
    r = TemplateRegistry()
    with pytest.raises(AITalkConfigError):
        r.register(TemplateSpec(name="x", system_prompt="s", output_format="xml"))


def test_register_empty_name_raises():
    r = TemplateRegistry()
    with pytest.raises(AITalkConfigError):
        r.register(TemplateSpec(name="", system_prompt="s"))


def test_register_overrides_previous():
    r = TemplateRegistry()
    r.register(TemplateSpec(name="x", system_prompt="old"))
    r.register(TemplateSpec(name="x", system_prompt="new"))
    assert r.get("x").system_prompt == "new"


def test_run_template_json_calls_structured_chat():
    fake = FakeLLMClient(structured_responses=[{"corrections": []}])
    ai = AITalk(llm_client=fake)
    result = ai.run_template("spellcheck", prompt="проверь")
    assert result == {"corrections": []}
    messages, fmt = fake.structured_calls[0]
    assert fmt == "json"
    assert messages[0].role == "system"
    assert "редактор" in messages[0].content.lower()


def test_run_template_text_calls_chat():
    fake = FakeLLMClient(chat_responses=["ответ"])
    ai = AITalk(llm_client=fake)
    ai.register_template(
        TemplateSpec(name="t", system_prompt="S", output_format="text")
    )
    result = ai.run_template("t", prompt="привет")
    assert result == "ответ"
    messages, _ = fake.chat_calls[0]
    assert messages[0].content == "S"


def test_run_template_unknown_raises_config_error():
    fake = FakeLLMClient()
    ai = AITalk(llm_client=fake)
    with pytest.raises(AITalkConfigError):
        ai.run_template("nope")


def test_run_template_with_source_reads_file():
    class FakeReader:
        def read(self, source):
            return "тело заметки"

    fake = FakeLLMClient(structured_responses=[{"tags": []}])
    ai = AITalk(llm_client=fake, file_reader=FakeReader())
    ai.run_template("obsidian_tagger", source="note.md")
    messages, _ = fake.structured_calls[0]
    assert "тело заметки" in messages[1].content


def test_per_template_temperature_used():
    fake = FakeLLMClient(chat_responses=["ok"])
    ai = AITalk(llm_client=fake)
    ai.register_template(
        TemplateSpec(
            name="t",
            system_prompt="S",
            output_format="text",
            temperature=0.3,
        )
    )
    ai.run_template("t", prompt="x")
    _, temp = fake.chat_calls[0]
    assert temp == 0.3


def test_explicit_temperature_overrides_template_temperature():
    fake = FakeLLMClient(chat_responses=["ok"])
    ai = AITalk(llm_client=fake)
    ai.register_template(
        TemplateSpec(
            name="t",
            system_prompt="S",
            output_format="text",
            temperature=0.3,
        )
    )
    ai.run_template("t", prompt="x", temperature=0.9)
    _, temp = fake.chat_calls[0]
    assert temp == 0.9


def test_custom_registry_passed_to_aitalk():
    r = TemplateRegistry()
    r.register(TemplateSpec(name="only_mine", system_prompt="S"))
    fake = FakeLLMClient(chat_responses=["ok"])
    ai = AITalk(llm_client=fake, template_registry=r)
    assert "only_mine" in ai.template_registry
    assert "spellcheck" not in ai.template_registry
