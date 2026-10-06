"""Регрессионные тесты: публичные импорты ai_talk не должны ломаться.

См. docs/COMPATIBILITY.md, раздел «Публичный API».
Эти тесты — контракт с внешними скриптами. Падение = сломанный релиз.
"""
import importlib
import re
from pathlib import Path


PUBLIC_TOP_LEVEL = (
    "AITalk",
    "ModelRole",
    "Prompts",
    "AITalkError",
    "AITalkConnectionError",
    "AITalkGenerationError",
)

INTERNAL_MODULES = (
    "ai_talk.adapters.facade",
    "ai_talk.application.prompts",
    "ai_talk.application.use_cases",
    "ai_talk.config.models",
    "ai_talk.domain.exceptions",
    "ai_talk.domain.interfaces",
    "ai_talk.infrastructure.actant_client",
    "ai_talk.infrastructure.custom_web_client",
    "ai_talk.infrastructure.file_reader",
    "ai_talk.infrastructure.ollama_client",
)


def test_top_level_exports():
    mod = importlib.import_module("ai_talk")
    for name in PUBLIC_TOP_LEVEL:
        assert hasattr(mod, name), f"ai_talk.{name} пропал из публичного API"


def test_internal_module_paths_stay_importable():
    """Внутренние модули импортируются напрямую — кто-то может их использовать."""
    for path in INTERNAL_MODULES:
        importlib.import_module(path)


def test_named_symbols_in_modules():
    from ai_talk.application.prompts import Prompts
    from ai_talk.application.use_cases import AskAIUseCase, GetTextUseCase
    from ai_talk.config.models import MODEL_REGISTRY, ModelRole
    from ai_talk.domain.exceptions import (
        AITalkConnectionError,
        AITalkError,
        AITalkGenerationError,
    )
    from ai_talk.domain.interfaces import IFileReader, ILLMClient, Message
    from ai_talk.infrastructure.file_reader import LocalFileReader
    from ai_talk.infrastructure.ollama_client import OllamaClient

    assert Prompts.SPELL_CHECKER
    assert Prompts.OBSIDIAN_TAGGER
    assert AskAIUseCase and GetTextUseCase
    assert MODEL_REGISTRY[ModelRole.FAST]
    assert issubclass(AITalkConnectionError, AITalkError)
    assert issubclass(AITalkGenerationError, AITalkError)
    assert ILLMClient and IFileReader and Message
    assert LocalFileReader and OllamaClient


def test_version_is_synced_with_pyproject():
    import ai_talk

    project_root = Path(ai_talk.__file__).resolve().parent.parent
    pyproject = project_root / "pyproject.toml"
    assert pyproject.exists(), "pyproject.toml не найден рядом с пакетом"

    text = pyproject.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "version не найден в pyproject.toml"
    assert ai_talk.__version__ == m.group(1), (
        f"ai_talk.__version__={ai_talk.__version__!r} != pyproject={m.group(1)!r}"
    )
