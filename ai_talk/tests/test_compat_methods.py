"""Регрессионные тесты: сигнатуры AITalk и значения ModelRole не меняются.

См. docs/COMPATIBILITY.md, раздел «Методы AITalk, которые нельзя менять».
"""
import inspect

from ai_talk import AITalk, ModelRole
from ai_talk.config.models import MODEL_REGISTRY


def _params(func):
    sig = inspect.signature(func)
    return {name: p for name, p in sig.parameters.items() if name != "self"}


def test_aitalk_init_signature():
    params = _params(AITalk.__init__)
    assert list(params) == [
        "model",
        "host",
        "custom_dir",
        "browser_instance_id",
        "config",
        "llm_client",
        "file_reader",
        "template_registry",
    ]
    # Позиционные (или position-or-keyword) параметры и их дефолты — фиксированы.
    assert params["model"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert params["model"].default == ModelRole.BASE
    assert params["host"].default == "http://localhost:11434"
    assert params["custom_dir"].default == "запросы_к_ии"
    assert params["browser_instance_id"].default == 0
    # Новые параметры — keyword-only и по умолчанию None.
    for name in ("config", "llm_client", "file_reader", "template_registry"):
        assert params[name].kind == inspect.Parameter.KEYWORD_ONLY
        assert params[name].default is None


def test_ask_ai_signature():
    params = _params(AITalk.ask_ai)
    assert list(params) == ["source", "system_prompt", "temperature"]
    assert params["system_prompt"].default == ""
    assert params["temperature"].default == 0.7


def test_ask_ai_structured_signature():
    params = _params(AITalk.ask_ai_structured)
    assert list(params) == ["source", "system_prompt", "response_format"]
    assert params["system_prompt"].default is inspect.Parameter.empty
    assert params["response_format"].default == "json"


def test_get_text_signature():
    params = _params(AITalk.get_text)
    assert list(params) == ["source"]


def test_model_role_values():
    assert ModelRole.FAST.value == "fast"
    assert ModelRole.SMART.value == "smart"
    assert ModelRole.BASE.value == "base"
    assert ModelRole.CUSTOM.value == "custom"
    assert ModelRole.WEB_DEEPSEEK.value == "web_deepseek"
    assert ModelRole.WEB_CHATGPT.value == "web_chatgpt"


def test_model_registry_has_all_roles():
    for role in ModelRole:
        assert role in MODEL_REGISTRY, f"{role} отсутствует в MODEL_REGISTRY"
