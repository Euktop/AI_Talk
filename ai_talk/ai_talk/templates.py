"""Реестр шаблонов AI_Talk.

Шаблон — это не просто системный промпт, а спецификация: формат вывода
(text/json), системный промпт, температура. Пользователь может
регистрировать свои шаблоны; они переопределяют встроенные с тем же именем.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

from ai_talk.application.prompts import Prompts
from ai_talk.errors import AITalkConfigError


@dataclass
class TemplateSpec:
    """Спецификация шаблона.

    name          — уникальное имя, по которому шаблон вызывается;
    system_prompt — системная инструкция для LLM;
    output_format — 'text' или 'json';
    temperature   — переопределяет AITalkConfig.temperature, если задана.
    """

    name: str
    system_prompt: str
    output_format: str = "text"
    temperature: Optional[float] = None


class TemplateRegistry:
    """Хранилище шаблонов. Регистрация с тем же именем перезаписывает."""

    def __init__(self) -> None:
        self._templates: Dict[str, TemplateSpec] = {}

    def register(self, spec: TemplateSpec) -> None:
        if not spec.name:
            raise AITalkConfigError("TemplateSpec.name не может быть пустым")
        if spec.output_format not in ("text", "json"):
            raise AITalkConfigError(
                "TemplateSpec.output_format должен быть 'text' или 'json', "
                "получено {0!r}".format(spec.output_format)
            )
        self._templates[spec.name] = spec

    def get(self, name: str) -> TemplateSpec:
        if name not in self._templates:
            raise AITalkConfigError(
                "Шаблон {0!r} не зарегистрирован. Доступные: {1}".format(
                    name, sorted(self._templates)
                )
            )
        return self._templates[name]

    def names(self) -> List[str]:
        return sorted(self._templates)

    def __contains__(self, name: str) -> bool:
        return name in self._templates


def default_registry() -> TemplateRegistry:
    """Возвращает НОВЫЙ реестр с встроенными шаблонами.

    Каждый вызов создаёт свежий объект — можно безопасно мутировать.
    """
    r = TemplateRegistry()
    r.register(TemplateSpec(
        name="spellcheck",
        system_prompt=Prompts.SPELL_CHECKER,
        output_format="json",
        temperature=0.1,
    ))
    r.register(TemplateSpec(
        name="obsidian_tagger",
        system_prompt=Prompts.OBSIDIAN_TAGGER,
        output_format="json",
        temperature=0.2,
    ))
    return r


__all__ = ["TemplateSpec", "TemplateRegistry", "default_registry"]
